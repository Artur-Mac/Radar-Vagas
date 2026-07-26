"""Remotive API Connector for PoC."""

import json
from datetime import datetime

import httpx

from poc.connectors.base import BaseConnector
from poc.schema import CanonicalJob, RawJobRecord


class RemotiveConnector(BaseConnector):
    """Connector for Remotive Public API (aggregator source)."""

    def __init__(self):
        super().__init__(source_name="remotive")
        self.api_url = "https://remotive.com/api/remote-jobs"

    def fetch_jobs(self, limit: int = 100) -> list[RawJobRecord]:
        records = []
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(self.api_url, params={"category": "data"})
                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("jobs", [])[:limit]
                    for job in jobs:
                        payload_str = json.dumps(job)
                        records.append(
                            RawJobRecord(
                                source_name=self.source_name,
                                source_job_id=str(job.get("id")),
                                content_hash=self.compute_hash(payload_str),
                                raw_payload=payload_str,
                                source_url=job.get("url"),
                            )
                        )
        except (httpx.HTTPError, TypeError, ValueError) as e:
            print(f"Error fetching from Remotive: {e}")
        return records

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        data = json.loads(raw_record.raw_payload)

        # Determine work arrangement
        location = data.get("candidate_required_location", "")
        work_arrangement = "remote"  # Remotive jobs are remote

        # Published timestamp
        published_at = None
        pub_str = data.get("publication_date")
        if pub_str:
            try:
                published_at = datetime.fromisoformat(pub_str)
            except (TypeError, ValueError):
                published_at = None

        return CanonicalJob(
            job_id=f"remotive_{raw_record.source_job_id}",
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
            country="Worldwide"
            if "anywhere" in location.lower() or "worldwide" in location.lower()
            else location,
            work_arrangement=work_arrangement,
            employment_type="full_time"
            if "full" in str(data.get("job_type")).lower()
            else "unknown",
            published_at=published_at,
            collected_at=raw_record.collected_at,
        )
