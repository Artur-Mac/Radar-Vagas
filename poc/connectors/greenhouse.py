"""Greenhouse Board API Connector for PoC."""

import json
from datetime import datetime
from typing import ClassVar

import httpx

from poc.connectors.base import BaseConnector, balanced_sample
from poc.schema import CanonicalJob, RawJobRecord


class GreenhouseConnector(BaseConnector):
    """Connector for Greenhouse ATS Public Job Board API."""

    DEFAULT_BOARDS: ClassVar[tuple[str, ...]] = (
        "canonical",
        "gitlab",
        "cloudflare",
        "datadog",
        "grafana",
        "cockroachlabs",
    )

    def __init__(self, target_boards: list[str] | None = None):
        super().__init__(source_name="greenhouse")
        self.target_boards = tuple(target_boards or self.DEFAULT_BOARDS)

    def fetch_jobs(self, limit: int = 100) -> list[RawJobRecord]:
        records_by_board: list[list[RawJobRecord]] = []
        with httpx.Client(timeout=15.0) as client:
            for board in self.target_boards:
                board_records: list[RawJobRecord] = []
                url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
                try:
                    res = client.get(url)
                    if res.status_code == 200:
                        data = res.json()
                        jobs = data.get("jobs", [])
                        for job in jobs:
                            job["_board_identifier"] = board
                            payload_str = json.dumps(job)
                            board_records.append(
                                RawJobRecord(
                                    source_name=self.source_name,
                                    source_job_id=f"{board}_{job.get('id')}",
                                    content_hash=self.compute_hash(payload_str),
                                    raw_payload=payload_str,
                                    source_url=job.get("absolute_url"),
                                )
                            )
                except (httpx.HTTPError, TypeError, ValueError) as e:
                    print(f"Error fetching Greenhouse board '{board}': {e}")
                records_by_board.append(board_records)
        return balanced_sample(records_by_board, limit)

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        data = json.loads(raw_record.raw_payload)

        location_dict = data.get("location", {})
        location_raw = (
            location_dict.get("name", "") if isinstance(location_dict, dict) else str(location_dict)
        )

        board = data.get("_board_identifier", "greenhouse_company")

        # Determine work arrangement
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
            source_name=self.source_name,
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
