"""Lever ATS Postings API connector."""

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

logger = logging.getLogger("radar_vagas.connectors.lever")


class LeverConnector:
    """Connector for a single Lever company's public postings.

    Each ``SourceConfig`` represents one company (e.g. ``spotify``, ``netflix``).
    The company identifier comes from ``config.company_identifier``.
    """

    def __init__(self, config: SourceConfig) -> None:
        self._config = config
        if not config.company_identifier:
            msg = f"LeverConnector requires company_identifier in config '{config.name}'"
            raise ValueError(msg)

    @property
    def source_config(self) -> SourceConfig:
        return self._config

    def fetch(self, client: httpx.Client, *, limit: int = 100) -> ConnectorResult:
        """Fetch raw job records from a single Lever company."""
        start = time.monotonic()
        errors: list[CollectionError] = []
        records: list[RawJobRecord] = []
        company = self._config.company_identifier

        policy = HttpPolicy(
            timeout=self._config.request_timeout,
            max_retries=self._config.max_retries,
            rate_limit_delay=self._config.rate_limit_delay,
        )

        url = f"{str(self._config.base_url).rstrip('/')}/{company}"
        try:
            response = polite_get(client, url, policy=policy, params={"mode": "json"})
            jobs = response.json()
            if not isinstance(jobs, list):
                jobs = []
            jobs = jobs[:limit]

            for job in jobs:
                try:
                    job["_company_identifier"] = company
                    payload_str = json.dumps(job)
                    records.append(
                        RawJobRecord(
                            source_name=self._config.name,
                            source_type=self._config.source_type,
                            source_job_id=f"{company}_{job.get('id')}",
                            content_hash=hashlib.sha256(payload_str.encode()).hexdigest(),
                            raw_payload=payload_str,
                            source_url=job.get("hostedUrl"),
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
            logger.warning("Lever fetch failed for company '%s': %s", company, exc)
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
        """Transform a Lever raw record into the canonical schema."""
        data = json.loads(raw_record.raw_payload)

        categories = data.get("categories", {})
        location_raw = categories.get("location", "")
        company = data.get("_company_identifier", "lever_company")

        loc_lower = location_raw.lower()
        if "remote" in loc_lower or "anywhere" in loc_lower:
            work_arrangement = "remote"
        elif "hybrid" in loc_lower:
            work_arrangement = "hybrid"
        else:
            work_arrangement = "on_site" if location_raw else "unknown"

        created_at = data.get("createdAt")
        published_at = None
        if created_at:
            try:
                published_at = datetime.fromtimestamp(created_at / 1000.0, tz=UTC)
            except (TypeError, ValueError, OSError):
                published_at = None

        description = data.get("descriptionPlain", "") or data.get("description", "")

        return CanonicalJob(
            job_id=f"lever_{raw_record.source_job_id}",
            source_name=self._config.name,
            source_job_id=raw_record.source_job_id,
            source_url=raw_record.source_url,
            application_url=data.get("applyUrl") or data.get("hostedUrl"),
            title_raw=data.get("text", ""),
            title_normalized=data.get("text", "").strip(),
            company_raw=company.capitalize(),
            company_normalized=company.capitalize(),
            description_raw=description,
            description_clean=description,
            location_raw=location_raw,
            work_arrangement=work_arrangement,
            published_at=published_at,
            collected_at=raw_record.collected_at,
        )
