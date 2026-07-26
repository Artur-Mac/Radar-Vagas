"""Lever API Connector for PoC."""

import json
from datetime import UTC, datetime
from typing import ClassVar

import httpx

from poc.connectors.base import BaseConnector, balanced_sample
from poc.schema import CanonicalJob, RawJobRecord


class LeverConnector(BaseConnector):
    """Connector for Lever ATS Public Postings API."""

    DEFAULT_COMPANIES: ClassVar[tuple[str, ...]] = (
        "spotify",
        "netflix",
        "palantir",
        "plaid",
    )

    def __init__(self, target_companies: list[str] | None = None):
        super().__init__(source_name="lever")
        self.target_companies = tuple(target_companies or self.DEFAULT_COMPANIES)

    def fetch_jobs(self, limit: int = 100) -> list[RawJobRecord]:
        records_by_company: list[list[RawJobRecord]] = []
        with httpx.Client(timeout=15.0) as client:
            for company in self.target_companies:
                company_records: list[RawJobRecord] = []
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                try:
                    res = client.get(url)
                    if res.status_code == 200:
                        jobs = res.json()
                        for job in jobs:
                            job["_company_identifier"] = company
                            payload_str = json.dumps(job)
                            company_records.append(
                                RawJobRecord(
                                    source_name=self.source_name,
                                    source_job_id=f"{company}_{job.get('id')}",
                                    content_hash=self.compute_hash(payload_str),
                                    raw_payload=payload_str,
                                    source_url=job.get("hostedUrl"),
                                )
                            )
                except (httpx.HTTPError, TypeError, ValueError) as e:
                    print(f"Error fetching Lever company '{company}': {e}")
                records_by_company.append(company_records)
        return balanced_sample(records_by_company, limit)

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
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

        createdAt = data.get("createdAt")
        published_at = None
        if createdAt:
            try:
                published_at = datetime.fromtimestamp(createdAt / 1000.0, tz=UTC)
            except (TypeError, ValueError, OSError):
                published_at = None

        description = data.get("descriptionPlain", "") or data.get("description", "")

        return CanonicalJob(
            job_id=f"lever_{raw_record.source_job_id}",
            source_name=self.source_name,
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
