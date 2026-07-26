"""Core ingestion pipeline service."""

import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from radar_vagas import __version__
from radar_vagas.domain.models import (
    ExactDuplicate,
    IngestionSummary,
    Pagination,
    QuarantinedRecord,
    RejectedRecord,
    RunManifest,
    RunState,
    SourceConfig,
    SourceRunSummary,
)
from radar_vagas.infrastructure.storage import LocalStorage
from radar_vagas.sources.registry import ConnectorRegistry

logger = logging.getLogger("radar_vagas.core.ingestion")

DATA_AI_REGEX = re.compile(
    r"\b(data|machine learning|ml|ai|artificial intelligence|analytics|mlops|llm|deep learning)\b",
    re.IGNORECASE,
)


@dataclass
class _SourceExecutionState:
    config: SourceConfig
    connector: Any
    summary: SourceRunSummary
    cursor: Pagination | None = None
    seen_page_urls: set[str] = None
    source_seen_ids: set[str] = None
    source_fetched: int = 0
    start_time: float = 0.0
    is_done: bool = False

    def __post_init__(self):
        if self.seen_page_urls is None:
            self.seen_page_urls = set()
        if self.source_seen_ids is None:
            self.source_seen_ids = set()
        self.start_time = time.monotonic()


class ConnectorRunner:
    """Service to execute connectors, apply minimal validation, and persist data."""

    def __init__(
        self,
        registry: ConnectorRegistry,
        storage: LocalStorage,
        client: httpx.Client,
    ) -> None:
        self.registry = registry
        self.storage = storage
        self.client = client

    def run(
        self,
        configs: list[SourceConfig],
        *,
        global_limit: int | None = None,
        per_source_limit: int | None = None,
        fail_fast: bool = False,
        persist: bool = True,
    ) -> RunManifest:
        """Execute a full ingestion run across multiple sources."""
        if global_limit is not None and global_limit <= 0:
            raise ValueError("global_limit must be a positive integer")
        if per_source_limit is not None and per_source_limit <= 0:
            raise ValueError("per_source_limit must be a positive integer")

        run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        started_at = datetime.now(UTC)

        if persist:
            self.storage.ensure_run_dirs(run_id)

        manifest = RunManifest(
            summary=IngestionSummary(
                run_id=run_id,
                started_at=started_at,
                finished_at=started_at,
                version=__version__,
                total_sources_requested=len(configs),
                total_sources_executed=0,
                global_limit=global_limit,
                per_source_limit=per_source_limit,
            )
        )

        global_fetched = 0
        global_seen_hashes: set[str] = set()

        execution_states: list[_SourceExecutionState] = []
        attempted_sources = 0

        # Initialize sources
        for config in configs:
            if not config.active:
                manifest.summary.sources[config.name] = SourceRunSummary(
                    source_name=config.name, state=RunState.disabled
                )
                continue

            attempted_sources += 1
            summary = SourceRunSummary(source_name=config.name, state=RunState.success)
            try:
                connector = self.registry.create(config)
                execution_states.append(
                    _SourceExecutionState(config=config, connector=connector, summary=summary)
                )
            except KeyError:
                logger.error("Connector not found for type %s", config.source_type)
                summary.state = RunState.invalid_configuration
                manifest.summary.sources[config.name] = summary
                if fail_fast:
                    self._mark_remaining_skipped(configs, manifest, RunState.skipped_fail_fast)
                    manifest.summary.total_sources_executed = attempted_sources
                    return self._finalize_manifest(manifest, start_time, persist)

        manifest.summary.total_sources_executed = attempted_sources

        # Round-Robin Fetch Loop
        while True:
            active_states = [s for s in execution_states if not s.is_done]
            if not active_states:
                break

            if global_limit is not None and global_fetched >= global_limit:
                logger.info("Global limit reached (%d). Stopping.", global_limit)
                for s in active_states:
                    s.summary.state = RunState.skipped_global_limit
                    s.is_done = True
                break

            for state in active_states:
                if global_limit is not None and global_fetched >= global_limit:
                    state.summary.state = RunState.skipped_global_limit
                    state.is_done = True
                    continue

                limit = 100
                if per_source_limit is not None:
                    limit = min(limit, per_source_limit - state.source_fetched)
                if global_limit is not None:
                    limit = min(limit, global_limit - global_fetched)

                if limit <= 0:
                    state.is_done = True
                    continue

                logger.info("Fetching from source: %s (limit: %d)", state.config.name, limit)
                try:
                    result = state.connector.fetch(self.client, limit=limit, cursor=state.cursor)
                except Exception:
                    logger.exception("Unexpected failure fetching %s", state.config.name)
                    state.summary.state = RunState.temporary_failure
                    state.is_done = True
                    if fail_fast:
                        self._handle_fail_fast(execution_states)
                        break
                    continue

                if result.errors:
                    logger.warning("Connector %s reported errors during fetch.", state.config.name)
                    state.summary.errors.extend(result.errors)
                    if result.records:
                        state.summary.state = RunState.partial
                    else:
                        state.summary.state = (
                            result.state
                            if hasattr(result, "state")
                            and result.state
                            in {RunState.temporary_failure, RunState.permanent_failure}
                            else RunState.temporary_failure
                        )

                if not result.records:
                    if state.source_fetched == 0 and not result.errors:
                        state.summary.state = RunState.empty
                    state.is_done = True
                    if state.summary.state == RunState.success:
                        state.summary.coverage_complete = True
                    continue

                for record in result.records:
                    state.source_fetched += 1
                    global_fetched += 1
                    state.summary.records_fetched += 1

                    # 1. Minimal Validation
                    rejection_reason = ""
                    if not record.source_job_id:
                        rejection_reason = "missing_source_job_id"
                    elif not record.source_url:
                        rejection_reason = "missing_source_url"
                    elif not record.raw_payload:
                        rejection_reason = "missing_raw_payload"
                    elif record.source_name != state.config.name:
                        rejection_reason = "source_name_mismatch"
                    elif record.source_type and record.source_type != state.config.source_type:
                        rejection_reason = "source_type_mismatch"

                    if rejection_reason:
                        manifest.rejected.append(
                            RejectedRecord(
                                source_name=state.config.name,
                                source_job_id=record.source_job_id,
                                reason=rejection_reason,
                            )
                        )
                        state.summary.records_rejected += 1
                        if persist:
                            try:
                                self.storage.save_quarantined_record(
                                    run_id=run_id,
                                    source_name=state.config.name,
                                    source_job_id=record.source_job_id,
                                    payload=record.raw_payload,
                                )
                            except OSError as exc:
                                manifest.quarantined.append(
                                    QuarantinedRecord(
                                        source_name=state.config.name,
                                        source_job_id=record.source_job_id,
                                        error_type=type(exc).__name__,
                                        message=str(exc),
                                        phase="quarantine_persistence",
                                        raw_payload=record.raw_payload,
                                    )
                                )
                                state.summary.records_quarantined += 1
                        continue

                    # 2. Exact Deduplication
                    is_duplicate = False
                    reason = ""
                    if record.source_job_id in state.source_seen_ids:
                        is_duplicate = True
                        reason = "same_run_source_job_id"
                    elif record.content_hash in global_seen_hashes:
                        is_duplicate = True
                        reason = "same_run_content_hash"

                    if is_duplicate:
                        manifest.duplicates.append(
                            ExactDuplicate(
                                source_name=state.config.name,
                                source_job_id=record.source_job_id,
                                reason=reason,
                            )
                        )
                        state.summary.records_duplicated += 1
                        continue

                    state.source_seen_ids.add(record.source_job_id)
                    global_seen_hashes.add(record.content_hash)

                    # 3. Data/AI Relevance Filter
                    is_relevant = bool(DATA_AI_REGEX.search(record.raw_payload))

                    # 4. Persistence
                    try:
                        if persist:
                            self.storage.save_raw_record(
                                run_id=run_id,
                                source_name=state.config.name,
                                source_job_id=record.source_job_id,
                                payload=record.raw_payload,
                            )
                        state.summary.records_valid += 1
                        if is_relevant:
                            state.summary.records_relevant += 1
                    except OSError as exc:
                        logger.error("Failed to persist record %s: %s", record.source_job_id, exc)
                        manifest.quarantined.append(
                            QuarantinedRecord(
                                source_name=state.config.name,
                                source_job_id=record.source_job_id,
                                error_type=type(exc).__name__,
                                message=str(exc),
                                phase="persistence",
                                raw_payload=record.raw_payload,
                            )
                        )
                        state.summary.records_quarantined += 1

                # Loop Control / Pagination
                if not result.next_page or not result.next_page.has_more:
                    state.is_done = True
                    if state.summary.state == RunState.success and not (
                        global_limit or per_source_limit
                    ):
                        state.summary.coverage_complete = True
                    continue

                next_page_url = result.next_page.next_page_url
                if next_page_url and next_page_url in state.seen_page_urls:
                    logger.warning("Pagination loop detected for %s. Stopping.", state.config.name)
                    state.is_done = True
                    continue

                if next_page_url:
                    state.seen_page_urls.add(next_page_url)
                state.cursor = result.next_page

        # Finalize states
        for state in execution_states:
            state.summary.duration_seconds = time.monotonic() - state.start_time
            if state.summary.state == RunState.success and state.source_fetched == 0:
                state.summary.state = RunState.empty
            elif state.summary.state == RunState.success and state.summary.errors:
                state.summary.state = RunState.partial

            manifest.summary.sources[state.config.name] = state.summary

        return self._finalize_manifest(manifest, start_time, persist)

    def _mark_remaining_skipped(
        self, configs: list[SourceConfig], manifest: RunManifest, state: RunState
    ):
        for config in configs:
            if config.name not in manifest.summary.sources:
                manifest.summary.sources[config.name] = SourceRunSummary(
                    source_name=config.name,
                    state=state if config.active else RunState.disabled,
                )

    def _handle_fail_fast(self, execution_states: list[_SourceExecutionState]):
        for state in execution_states:
            if not state.is_done:
                state.summary.state = RunState.skipped_fail_fast
                state.is_done = True

    def _finalize_manifest(
        self, manifest: RunManifest, start_time: float, persist: bool
    ) -> RunManifest:
        manifest.summary.finished_at = datetime.now(UTC)
        manifest.summary.duration_seconds = time.monotonic() - start_time

        for src_summary in manifest.summary.sources.values():
            manifest.summary.total_fetched += src_summary.records_fetched
            manifest.summary.total_valid += src_summary.records_valid
            manifest.summary.total_rejected += src_summary.records_rejected
            manifest.summary.total_quarantined += src_summary.records_quarantined
            manifest.summary.total_duplicated += src_summary.records_duplicated
            manifest.summary.total_relevant += src_summary.records_relevant

        if persist:
            self.storage.save_manifest(manifest.summary.run_id, manifest)

        return manifest
