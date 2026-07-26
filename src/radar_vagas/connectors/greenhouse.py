"""Greenhouse ATS Board API connector."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime

import httpx

from radar_vagas.domain.models import (
    CanonicalJob,
    CollectionError,
    ConnectorResult,
    Pagination,
    RawJobRecord,
    SourceConfig,
)
from radar_vagas.infrastructure.http import HttpPolicy, polite_get

logger = logging.getLogger("radar_vagas.connectors.greenhouse")


class GreenhouseConnector:
    """Connector for a single Greenhouse ATS public job board.

    Each ``SourceConfig`` represents one board (e.g. ``gitlab``, ``datadog``).
    The board identifier comes from ``config.board_identifier``.
    """

    def __init__(self, config: SourceConfig) -> None:
        self._config = config
        if not config.board_identifier:
            msg = f"GreenhouseConnector requires board_identifier in config '{config.name}'"
            raise ValueError(msg)

    @property
    def source_config(self) -> SourceConfig:
        return self._config

    def fetch(
        self, client: httpx.Client, *, limit: int = 100, cursor: Pagination | None = None
    ) -> ConnectorResult:
        """Fetch raw job records from a single Greenhouse board."""
        start = time.monotonic()
        errors: list[CollectionError] = []
        records: list[RawJobRecord] = []
        board = self._config.board_identifier
        next_page = Pagination(has_more=False)

        policy = HttpPolicy(
            timeout=self._config.request_timeout,
            max_retries=self._config.max_retries,
            rate_limit_delay=self._config.rate_limit_delay,
        )

        url = f"{str(self._config.base_url).rstrip('/')}/{board}/jobs"
        try:
            response = polite_get(client, url, policy=policy, params={"content": "true"})
            data = response.json()
            jobs = data.get("jobs", [])[:limit]

            for job in jobs:
                try:
                    job["_board_identifier"] = board
                    payload_str = json.dumps(job)
                    records.append(
                        RawJobRecord(
                            source_name=self._config.name,
                            source_type=self._config.source_type,
                            source_job_id=f"{board}_{job.get('id')}",
                            content_hash=hashlib.sha256(payload_str.encode()).hexdigest(),
                            raw_payload=payload_str,
                            source_url=job.get("absolute_url"),
                        )
                    )
                except (TypeError, ValueError, KeyError) as exc:
                    errors.append(
                        CollectionError(
                            source_name=self._config.name,
                            phase="fetch",
                            message=f"Failed to parse record: {exc}",
                        )
                    )
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            logger.warning("Greenhouse fetch failed for board '%s': %s", board, exc)
            errors.append(
                CollectionError(
                    source_name=self._config.name,
                    phase="fetch",
                    message=str(exc),
                )
            )

        return ConnectorResult(
            source_name=self._config.name,
            records=records,
            records_fetched=len(records),
            records_failed=len(errors),
            errors=errors,
            duration_seconds=time.monotonic() - start,
            next_page=next_page,
        )

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        """Transform a Greenhouse raw record into the canonical schema."""
        data = json.loads(raw_record.raw_payload)

        location_dict = data.get("location", {})
        location_raw = (
            location_dict.get("name", "") if isinstance(location_dict, dict) else str(location_dict)
        )

        board = data.get("_board_identifier", "greenhouse_company")

        loc_lower = location_raw.lower()
        if "remote" in loc_lower or "anywhere" in loc_lower:
            work_arrangement = "remote"
        elif "hybrid" in loc_lower:
            work_arrangement = "hybrid"
        else:
            work_arrangement = "on_site" if location_raw else "unknown"

        updated_at = data.get("updated_at")
        published_at = None
        if updated_at:
            try:
                published_at = datetime.fromisoformat(updated_at)
            except (TypeError, ValueError):
                published_at = None

        return CanonicalJob(
            job_id=f"greenhouse_{raw_record.source_job_id}",
            source_name=self._config.name,
            source_job_id=raw_record.source_job_id,
            source_url=raw_record.source_url,
            application_url=data.get("absolute_url"),
            title_raw=data.get("title", ""),
            title_normalized=data.get("title", "").strip(),
            company_raw=board.capitalize(),
            company_normalized=board.capitalize(),
            description_raw=data.get("content", ""),
            description_clean=data.get("content", ""),
            location_raw=location_raw,
            work_arrangement=work_arrangement,
            published_at=published_at,
            collected_at=raw_record.collected_at,
        )
