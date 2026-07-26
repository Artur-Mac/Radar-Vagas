import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from radar_vagas.domain.models import RawJobRecord, RunManifest
from radar_vagas.infrastructure.history import HistoricalStorage
from radar_vagas.infrastructure.storage import LocalStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportErrorDetail:
    run_dir: str
    error_type: str
    message: str


@dataclass
class ImportReport:
    discovered_runs: int = 0
    imported_runs: int = 0
    skipped_runs: int = 0
    failed_runs: int = 0
    imported_records: int = 0
    rejected_records: int = 0
    errors: list[ImportErrorDetail] = field(default_factory=list)


class HistoryService:
    def __init__(self, storage: LocalStorage, history: HistoricalStorage):
        self.storage = storage
        self.history = history

    def import_all_runs(self) -> ImportReport:
        """Finds all local runs and imports them into historical storage."""
        report = ImportReport()
        if not self.storage.runs_dir.exists():
            return report

        run_dirs = sorted(self.storage.runs_dir.iterdir(), key=lambda d: d.name)
        report.discovered_runs = sum(1 for d in run_dirs if d.is_dir())

        for run_dir in run_dirs:
            if not run_dir.is_dir():
                continue

            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                logger.warning(f"Run {run_dir.name} has no manifest.json. Skipping.")
                report.skipped_runs += 1
                continue

            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = RunManifest.model_validate(manifest_data)

                # Check if already imported
                res = self.history.conn.execute(
                    "SELECT run_id FROM ingestion_runs WHERE run_id = ?", [manifest.summary.run_id]
                ).fetchone()

                if res:
                    logger.debug(f"Run {manifest.summary.run_id} already imported.")
                    report.skipped_runs += 1
                    continue

                # Load valid records and capture rejection count
                records, rejections = self._load_run_records(run_dir, manifest)
                report.rejected_records += rejections
                if rejections:
                    raise ValueError(
                        f"Run contains {rejections} malformed raw record(s); "
                        "the run was not imported"
                    )

                self.history.import_run(manifest, records)
                logger.info(
                    f"Imported run {manifest.summary.run_id} with {len(records)} valid records."
                )
                report.imported_runs += 1
                report.imported_records += len(records)

            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to import run {run_dir.name}: {e}")
                report.failed_runs += 1
                report.errors.append(
                    ImportErrorDetail(
                        run_dir=run_dir.name,
                        error_type=type(e).__name__,
                        message=str(e),
                    )
                )

        return report

    def _load_run_records(
        self, run_dir: Path, manifest: RunManifest
    ) -> tuple[list[RawJobRecord], int]:
        """Load both legacy payload-only files and newer record envelopes.
        Returns a tuple of (valid_records, rejected_count).
        """
        records: list[RawJobRecord] = []
        rejected_count = 0
        raw_dir = run_dir / "raw"
        if not raw_dir.exists():
            return records, rejected_count

        source_names = sorted(manifest.summary.sources, key=len, reverse=True)
        for record_file in sorted(raw_dir.glob("*.json")):
            try:
                payload = record_file.read_text(encoding="utf-8")
                parsed = json.loads(payload)

                if isinstance(parsed, dict) and {
                    "source_name",
                    "source_job_id",
                    "raw_payload",
                }.issubset(parsed):
                    records.append(RawJobRecord.model_validate(parsed))
                    continue

                source_name = next(
                    (name for name in source_names if record_file.stem.startswith(f"{name}-")),
                    None,
                )
                if source_name is None:
                    raise ValueError(f"Cannot identify source for {record_file.name}")

                source_job_id = record_file.stem.removeprefix(f"{source_name}-")
                source_url = self._extract_source_url(parsed)
                if not source_url:
                    raise ValueError(f"Cannot identify source URL for {record_file.name}")

                records.append(
                    RawJobRecord(
                        source_name=source_name,
                        source_job_id=source_job_id,
                        source_url=source_url,
                        raw_payload=payload,
                        collected_at=manifest.summary.started_at,
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Malformed record {record_file.name} in run {run_dir.name}: {e}")
                rejected_count += 1

        return records, rejected_count

    def run_exists(self, run_id: str) -> bool:
        return (
            self.history.conn.execute(
                "SELECT 1 FROM ingestion_runs WHERE run_id = ?", [run_id]
            ).fetchone()
            is not None
        )

    @staticmethod
    def _extract_source_url(payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None
        for key in ("url", "absolute_url", "hostedUrl", "applyUrl"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def get_run_records(self, run_id: str) -> list[RawJobRecord]:
        """Replays all raw job records from a specific historical run."""
        # Join with source_jobs to get source_url
        rows = self.history.conn.execute(
            """
            SELECT
                o.source_name,
                o.source_job_id,
                o.content_hash,
                o.observed_at,
                COALESCE(o.source_url, j.source_url),
                o.source_type
            FROM source_job_observations o
            LEFT JOIN source_jobs j
                ON o.source_name = j.source_name AND o.source_job_id = j.source_job_id
            WHERE o.run_id = ?
            ORDER BY o.source_name, o.source_job_id
            """,
            [run_id],
        ).fetchall()

        records = []
        for src_name, job_id, content_hash, observed_at, source_url, source_type in rows:
            payload = self.history.read_blob(content_hash)

            records.append(
                RawJobRecord(
                    source_name=src_name,
                    source_job_id=job_id,
                    source_url=source_url,
                    raw_payload=payload,
                    content_hash=content_hash,
                    collected_at=observed_at,
                    source_type=source_type,
                )
            )

        return records
