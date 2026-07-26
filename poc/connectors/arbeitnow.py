"""Arbeitnow API Connector for PoC."""

import json
from datetime import UTC, datetime

import httpx

from poc.connectors.base import BaseConnector
from poc.schema import CanonicalJob, RawJobRecord


class ArbeitnowConnector(BaseConnector):
    """Connector for Arbeitnow Public API (aggregator source)."""

    def __init__(self):
        super().__init__(source_name="arbeitnow")
        self.api_url = "https://www.arbeitnow.com/api/job-board-api"

    def fetch_jobs(self, limit: int = 100) -> list[RawJobRecord]:
        records = []
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(self.api_url)
                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("data", [])[:limit]
                    for job in jobs:
                        payload_str = json.dumps(job)
                        records.append(
                            RawJobRecord(
                                source_name=self.source_name,
                                source_job_id=str(job.get("slug")),
                                content_hash=self.compute_hash(payload_str),
                                raw_payload=payload_str,
                                source_url=job.get("url"),
                            )
                        )
        except (httpx.HTTPError, TypeError, ValueError) as e:
            print(f"Error fetching from Arbeitnow: {e}")
        return records

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        data = json.loads(raw_record.raw_payload)

        is_remote = data.get("remote", False)
        work_arrangement = "remote" if is_remote else "on_site"

        location = data.get("location", "")

        # Published timestamp
        pub_ts = data.get("created_at")
        published_at = None
        if pub_ts:
            try:
                published_at = datetime.fromtimestamp(pub_ts, tz=UTC)
            except (TypeError, ValueError, OSError):
                published_at = None

        return CanonicalJob(
            job_id=f"arbeitnow_{raw_record.source_job_id}",
            source_name=self.source_name,
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
            work_arrangement=work_arrangement,
            published_at=published_at,
            collected_at=raw_record.collected_at,
        )
