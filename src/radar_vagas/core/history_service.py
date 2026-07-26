import json
import logging
from pathlib import Path

from radar_vagas.domain.models import RawJobRecord, RunManifest
from radar_vagas.infrastructure.history import HistoricalStorage
from radar_vagas.infrastructure.storage import LocalStorage

logger = logging.getLogger(__name__)


class HistoryService:
    def __init__(self, storage: LocalStorage, history: HistoricalStorage):
        self.storage = storage
        self.history = history

    def import_all_runs(self) -> int:
        """Finds all local runs and imports them into historical storage."""
        imported_count = 0
        if not self.storage.runs_dir.exists():
            return 0

        # We need to sort by started_at if possible, but run directories are timestamps like 20240101_120000
        run_dirs = sorted(self.storage.runs_dir.iterdir(), key=lambda d: d.name)

        for run_dir in run_dirs:
            if not run_dir.is_dir():
                continue

            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                logger.warning(f"Run {run_dir.name} has no manifest.json. Skipping.")
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
                    continue

                records = self._load_run_records(run_dir, manifest)

                self.history.import_run(manifest, records)
                logger.info(
                    f"Imported run {manifest.summary.run_id} with {len(records)} valid records."
                )
                imported_count += 1

            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to import run {run_dir.name}: {e}")

        return imported_count

    def _load_run_records(self, run_dir: Path, manifest: RunManifest) -> list[RawJobRecord]:
        """Load both legacy payload-only files and newer record envelopes."""
        records: list[RawJobRecord] = []
        raw_dir = run_dir / "raw"
        if not raw_dir.exists():
            return records

        source_names = sorted(manifest.summary.sources, key=len, reverse=True)
        for record_file in sorted(raw_dir.glob("*.json")):
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
                )
            )
        return records

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
                COALESCE(o.source_url, j.source_url)
            FROM source_job_observations o
            JOIN source_jobs j ON o.source_name = j.source_name AND o.source_job_id = j.source_job_id
            WHERE o.run_id = ?
            """,
            [run_id],
        ).fetchall()

        records = []
        for src_name, job_id, content_hash, observed_at, source_url in rows:
            payload = self.history.read_blob(content_hash)

            records.append(
                RawJobRecord(
                    source_name=src_name,
                    source_job_id=job_id,
                    source_url=source_url,
                    raw_payload=payload,
                    content_hash=content_hash,
                    collected_at=observed_at,
                )
            )

        return records
