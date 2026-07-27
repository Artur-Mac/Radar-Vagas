import json
import logging
from dataclasses import dataclass, field
from typing import Any

from radar_vagas.core.normalization.adapters.registry import NormalizationAdapterRegistry
from radar_vagas.domain.canonical import CanonicalJobPost
from radar_vagas.domain.models import HistoricalQuarantineRecord
from radar_vagas.infrastructure.history import HistoricalStorage

logger = logging.getLogger(__name__)


@dataclass
class NormalizationReport:
    observations_discovered: int = 0
    records_normalized: int = 0
    records_skipped: int = 0
    records_rejected: int = 0
    records_quarantined: int = 0
    counts_by_source: dict[str, int] = field(default_factory=dict)
    counts_by_role_family: dict[str, int] = field(default_factory=dict)
    counts_by_seniority: dict[str, int] = field(default_factory=dict)
    missing_canonical_fields: dict[str, int] = field(
        default_factory=lambda: {
            "company_name": 0,
            "job_title": 0,
            "location_raw": 0,
            "country_code": 0,
            "work_arrangement": 0,
            "employment_type": 0,
            "role_family": 0,
            "seniority": 0,
            "language": 0,
            "published_at": 0,
        }
    )
    elapsed_seconds: float = 0.0


class NormalizationService:
    """Service orchestrating batch job normalization across historical observations."""

    def __init__(
        self,
        history: HistoricalStorage,
        registry: NormalizationAdapterRegistry | None = None,
    ) -> None:
        self.history = history
        self.registry = registry or NormalizationAdapterRegistry()

    def normalize_batch(
        self,
        run_id: str | None = None,
        source_name: str | None = None,
        limit: int | None = None,
        rule_version: str = "1.0.0",
        dry_run: bool = False,
    ) -> NormalizationReport:
        with self.history.lock:
            return self._normalize_batch(
                run_id=run_id,
                source_name=source_name,
                limit=limit,
                rule_version=rule_version,
                dry_run=dry_run,
            )

    def _normalize_batch(
        self,
        run_id: str | None = None,
        source_name: str | None = None,
        limit: int | None = None,
        rule_version: str = "1.0.0",
        dry_run: bool = False,
    ) -> NormalizationReport:
        import time

        start_time = time.monotonic()
        report = NormalizationReport()

        # Query eligible observations along with latest cleaned text
        sql = """
            SELECT
                obs.observation_id,
                obs.source_name,
                obs.source_job_id,
                obs.run_id,
                obs.content_hash,
                obs.source_type,
                c.cleaned_id,
                c.cleaned_text
            FROM source_job_observations obs
            LEFT JOIN (
                SELECT cleaned_id, observation_id, cleaned_text
                FROM cleaned_source_text
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY observation_id
                    ORDER BY created_at DESC, transformation_version DESC, cleaned_id DESC
                ) = 1
            ) c ON obs.observation_id = c.observation_id
        """
        where_clauses: list[str] = []
        params: list[Any] = []

        if run_id:
            where_clauses.append("obs.run_id = ?")
            params.append(run_id)

        if source_name:
            where_clauses.append("obs.source_name = ?")
            params.append(source_name)

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += " ORDER BY obs.observed_at ASC, obs.observation_id ASC"

        rows = self.history.conn.execute(sql, params).fetchall()
        report.observations_discovered = len(rows)

        if not rows:
            report.elapsed_seconds = time.monotonic() - start_time
            return report

        # Fetch set of already processed observation IDs for this rule version
        existing_rows = self.history.conn.execute(
            "SELECT observation_id FROM normalized_job_records WHERE normalization_rule_version = ?",
            [rule_version],
        ).fetchall()
        processed_obs_ids = {r[0] for r in existing_rows}

        pending_rows = []
        for row in rows:
            if row[0] in processed_obs_ids:
                report.records_skipped += 1
            else:
                pending_rows.append(row)
        if limit is not None:
            pending_rows = pending_rows[:limit]

        records_to_save: list[CanonicalJobPost] = []

        for r in pending_rows:
            obs_id, s_name, s_job_id, r_id, content_hash, s_type, cleaned_id, cleaned_text = r

            try:
                raw_payload_str = self.history.read_blob(content_hash)
                payload = json.loads(raw_payload_str)
            except Exception as e:  # noqa: BLE001
                report.records_rejected += 1
                report.records_quarantined += 1
                if not dry_run:
                    self.history.quarantine_record(
                        HistoricalQuarantineRecord(
                            run_id=r_id,
                            source_name=s_name,
                            source_job_id=s_job_id,
                            failure_phase="normalize",
                            error_type=type(e).__name__,
                            message=f"Failed to read/parse raw blob for hash {content_hash}: {e}",
                            raw_content_hash=content_hash,
                            raw_payload=None,
                        )
                    )
                continue

            try:
                adapter = self.registry.get_adapter(
                    s_name or s_type or "", rule_version=rule_version
                )
                canonical = adapter.normalize_payload(
                    payload=payload,
                    observation_id=obs_id,
                    raw_content_hash=content_hash,
                    source_name=s_name,
                    source_job_id=s_job_id,
                    cleaned_id=cleaned_id,
                    cleaned_text=cleaned_text,
                )
                records_to_save.append(canonical)

                # Metrics recording
                report.records_normalized += 1
                report.counts_by_source[s_name] = report.counts_by_source.get(s_name, 0) + 1

                rf_val = canonical.role_family.value if canonical.role_family else "unclassified"
                report.counts_by_role_family[rf_val] = (
                    report.counts_by_role_family.get(rf_val, 0) + 1
                )

                sen_val = canonical.seniority.value if canonical.seniority else "unclassified"
                report.counts_by_seniority[sen_val] = report.counts_by_seniority.get(sen_val, 0) + 1

                # Check missing canonical fields
                for field in (
                    "company_name",
                    "job_title",
                    "location_raw",
                    "country_code",
                    "work_arrangement",
                    "employment_type",
                    "role_family",
                    "seniority",
                    "language",
                    "published_at",
                ):
                    if getattr(canonical, field) is None:
                        report.missing_canonical_fields[field] += 1

            except Exception as e:  # noqa: BLE001
                report.records_rejected += 1
                report.records_quarantined += 1
                if not dry_run:
                    self.history.quarantine_record(
                        HistoricalQuarantineRecord(
                            run_id=r_id,
                            source_name=s_name,
                            source_job_id=s_job_id,
                            failure_phase="normalize",
                            error_type=type(e).__name__,
                            message=f"Normalization adapter failed: {e}",
                            raw_content_hash=content_hash,
                            raw_payload=raw_payload_str[:1000],
                        )
                    )

        if not dry_run and records_to_save:
            self.history.save_normalized_records(records_to_save)

        report.elapsed_seconds = time.monotonic() - start_time
        return report
