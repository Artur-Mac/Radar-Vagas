"""Core ingestion pipeline service."""

import logging
import re
import time
import uuid
from datetime import UTC, datetime

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

# Deterministic filter for Data/AI Relevance
# Looks for keywords related to data, analytics, machine learning, ai, mlops.
DATA_AI_REGEX = re.compile(
    r"\b(data|machine learning|ml|ai|artificial intelligence|analytics|mlops|llm|deep learning)\b",
    re.IGNORECASE,
)


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
        persist: bool = True,
    ) -> RunManifest:
        """Execute a full ingestion run across multiple sources."""
        run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        started_at = datetime.now(UTC)

        if persist:
            self.storage.ensure_run_dirs(run_id)

        manifest = RunManifest(
            summary=IngestionSummary(
                run_id=run_id,
                started_at=started_at,
                finished_at=started_at,  # Updated at the end
                version=__version__,
                total_sources_requested=len(configs),
                total_sources_executed=0,
                global_limit=global_limit,
                per_source_limit=per_source_limit,
            )
        )

        global_fetched = 0
        global_seen_hashes: set[str] = set()

        for config in configs:
            if global_limit is not None and global_fetched >= global_limit:
                logger.info("Global limit reached (%d). Stopping.", global_limit)
                break

            if not config.active:
                manifest.summary.sources[config.name] = SourceRunSummary(
                    source_name=config.name, state=RunState.disabled
                )
                continue

            manifest.summary.total_sources_executed += 1
            source_summary = SourceRunSummary(source_name=config.name, state=RunState.success)
            source_start = time.monotonic()

            logger.info("Starting collection for source: %s", config.name)

            try:
                connector = self.registry.create(config)
            except KeyError:
                logger.error("Connector not found for type %s", config.source_type)
                source_summary.state = RunState.permanent_failure
                manifest.summary.sources[config.name] = source_summary
                continue

            cursor: Pagination | None = None
            seen_page_urls: set[str] = set()
            source_fetched = 0
            # Track duplicates per source across pagination loops within this run
            source_seen_ids: set[str] = set()

            while True:
                # Calculate how many we can still fetch
                limit = 100
                if per_source_limit is not None:
                    limit = min(limit, per_source_limit - source_fetched)
                if global_limit is not None:
                    limit = min(limit, global_limit - global_fetched)

                if limit <= 0:
                    break

                try:
                    result = connector.fetch(self.client, limit=limit, cursor=cursor)
                except Exception:  # Connector boundary: isolate third-party implementations.
                    logger.exception("Unexpected failure fetching %s", config.name)
                    source_summary.state = RunState.temporary_failure
                    break

                if result.errors:
                    logger.warning("Connector %s reported errors during fetch.", config.name)
                    source_summary.errors.extend(result.errors)
                    if result.records:
                        source_summary.state = RunState.partial
                    else:
                        source_summary.state = (
                            result.state
                            if result.state
                            in {RunState.temporary_failure, RunState.permanent_failure}
                            else RunState.temporary_failure
                        )

                if not result.records:
                    if source_fetched == 0 and not result.errors:
                        source_summary.state = RunState.empty
                    break

                for record in result.records:
                    source_fetched += 1
                    global_fetched += 1
                    source_summary.records_fetched += 1

                    # 1. Minimal Validation
                    rejection_reason = ""
                    if not record.source_job_id:
                        rejection_reason = "missing_source_job_id"
                    elif not record.source_url:
                        rejection_reason = "missing_source_url"
                    elif not record.raw_payload:
                        rejection_reason = "missing_raw_payload"

                    if rejection_reason:
                        manifest.rejected.append(
                            RejectedRecord(
                                source_name=config.name,
                                source_job_id=record.source_job_id,
                                reason=rejection_reason,
                            )
                        )
                        source_summary.records_rejected += 1
                        if persist:
                            try:
                                self.storage.save_quarantined_record(
                                    run_id=run_id,
                                    source_name=config.name,
                                    source_job_id=record.source_job_id,
                                    payload=record.raw_payload,
                                )
                            except OSError as exc:
                                logger.error(
                                    "Failed to persist rejected record %s: %s",
                                    record.source_job_id,
                                    exc,
                                )
                                manifest.quarantined.append(
                                    QuarantinedRecord(
                                        source_name=config.name,
                                        source_job_id=record.source_job_id,
                                        error_type=type(exc).__name__,
                                        message=str(exc),
                                        phase="quarantine_persistence",
                                        raw_payload=record.raw_payload,
                                    )
                                )
                                source_summary.records_quarantined += 1
                        continue

                    # 2. Exact Deduplication
                    is_duplicate = False
                    reason = ""
                    if record.source_job_id in source_seen_ids:
                        is_duplicate = True
                        reason = "same_run_source_job_id"
                    elif record.content_hash in global_seen_hashes:
                        is_duplicate = True
                        reason = "same_run_content_hash"

                    if is_duplicate:
                        manifest.duplicates.append(
                            ExactDuplicate(
                                source_name=config.name,
                                source_job_id=record.source_job_id,
                                reason=reason,
                            )
                        )
                        source_summary.records_duplicated += 1
                        continue

                    source_seen_ids.add(record.source_job_id)
                    global_seen_hashes.add(record.content_hash)

                    # 3. Data/AI Relevance Filter
                    is_relevant = bool(DATA_AI_REGEX.search(record.raw_payload))

                    # 4. Persistence
                    try:
                        if persist:
                            self.storage.save_raw_record(
                                run_id=run_id,
                                source_name=config.name,
                                source_job_id=record.source_job_id,
                                payload=record.raw_payload,
                            )
                        source_summary.records_valid += 1
                        if is_relevant:
                            source_summary.records_relevant += 1
                    except OSError as exc:
                        logger.error("Failed to persist record %s: %s", record.source_job_id, exc)
                        manifest.quarantined.append(
                            QuarantinedRecord(
                                source_name=config.name,
                                source_job_id=record.source_job_id,
                                error_type=type(exc).__name__,
                                message=str(exc),
                                phase="persistence",
                                raw_payload=record.raw_payload,
                            )
                        )
                        source_summary.records_quarantined += 1

                # Loop Control / Pagination
                if not result.next_page or not result.next_page.has_more:
                    break

                next_page_url = result.next_page.next_page_url
                if next_page_url and next_page_url in seen_page_urls:
                    logger.warning("Pagination loop detected for %s. Stopping.", config.name)
                    break

                if next_page_url:
                    seen_page_urls.add(next_page_url)
                cursor = result.next_page

            # End of source execution
            source_summary.duration_seconds = time.monotonic() - source_start
            if source_summary.state == RunState.success and source_fetched == 0:
                source_summary.state = RunState.empty
            elif source_summary.state == RunState.success and source_summary.errors:
                source_summary.state = RunState.partial

            manifest.summary.sources[config.name] = source_summary

        # End of overall execution
        manifest.summary.finished_at = datetime.now(UTC)
        manifest.summary.duration_seconds = time.monotonic() - start_time

        # Aggregate totals
        for src_summary in manifest.summary.sources.values():
            manifest.summary.total_fetched += src_summary.records_fetched
            manifest.summary.total_valid += src_summary.records_valid
            manifest.summary.total_rejected += src_summary.records_rejected
            manifest.summary.total_quarantined += src_summary.records_quarantined
            manifest.summary.total_duplicated += src_summary.records_duplicated
            manifest.summary.total_relevant += src_summary.records_relevant

        # Save manifest
        if persist:
            self.storage.save_manifest(run_id, manifest)

        return manifest
