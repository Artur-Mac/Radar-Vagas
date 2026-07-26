"""Arbeitnow aggregator API connector."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime

import httpx

from radar_vagas.domain.models import (
    CanonicalJob,
    CollectionError,
    ConnectorResult,
    RawJobRecord,
    SourceConfig,
)
from radar_vagas.infrastructure.http import HttpPolicy, polite_get

logger = logging.getLogger("radar_vagas.connectors.arbeitnow")


class ArbeitnowConnector:
    """Connector for the Arbeitnow public job board API."""

    def __init__(self, config: SourceConfig) -> None:
        self._config = config

    @property
    def source_config(self) -> SourceConfig:
        return self._config

    def fetch(self, client: httpx.Client, *, limit: int = 100) -> ConnectorResult:
        """Fetch raw job records from Arbeitnow API."""
        start = time.monotonic()
        errors: list[CollectionError] = []
        records: list[RawJobRecord] = []

        policy = HttpPolicy(
            timeout=self._config.request_timeout,
            max_retries=self._config.max_retries,
            rate_limit_delay=self._config.rate_limit_delay,
        )

        try:
            response = polite_get(client, str(self._config.base_url), policy=policy)
            data = response.json()
            jobs = data.get("data", [])[:limit]

            for job in jobs:
                try:
                    payload_str = json.dumps(job)
                    records.append(
                        RawJobRecord(
                            source_name=self._config.name,
                            source_type=self._config.source_type,
                            source_job_id=str(job.get("slug")),
                            content_hash=hashlib.sha256(payload_str.encode()).hexdigest(),
                            raw_payload=payload_str,
                            source_url=job.get("url"),
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
            logger.warning("Arbeitnow fetch failed: %s", exc)
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
        )

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        """Transform an Arbeitnow raw record into the canonical schema."""
        data = json.loads(raw_record.raw_payload)

        is_remote = data.get("remote", False)
        location = data.get("location", "")

        published_at = None
        pub_ts = data.get("created_at")
        if pub_ts:
            try:
                published_at = datetime.fromtimestamp(pub_ts, tz=UTC)
            except (TypeError, ValueError, OSError):
                published_at = None

        return CanonicalJob(
            job_id=f"arbeitnow_{raw_record.source_job_id}",
            source_name=self._config.name,
            source_job_id=raw_record.source_job_id,
            source_url=raw_record.source_url,
            application_url=data.get("url"),
            title_raw=data.get("title", ""),
            title_normalized=data.get("title", "").strip(),
            company_raw=data.get("company_name", ""),
            company_normalized=data.get("company_name", "").strip(),
            description_raw=data.get("description", ""),
            description_clean=data.get("description", ""),
            location_raw=location,
            work_arrangement="remote" if is_remote else "on_site",
            published_at=published_at,
            collected_at=raw_record.collected_at,
        )
