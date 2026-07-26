import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Self

import duckdb

from radar_vagas.domain.models import (
    BackupManifest,
    CleanedSourceText,
    HistoricalQuarantineRecord,
    RawJobRecord,
    RetentionPolicy,
    RetentionReport,
    RunManifest,
)

logger = logging.getLogger(__name__)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class MigrationTamperedError(ValueError):
    """Raised when an already applied migration script checksum differs from code."""


@dataclass(frozen=True)
class IntegrityReport:
    total_database_blobs: int
    missing_files: tuple[str, ...]
    corrupt_files: tuple[str, ...]
    missing_metadata: tuple[str, ...]
    orphan_database_blobs: tuple[str, ...]
    orphan_files: tuple[str, ...]
    invalid_blob_paths: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not any(
            (
                self.missing_files,
                self.corrupt_files,
                self.missing_metadata,
                self.orphan_database_blobs,
                self.orphan_files,
                self.invalid_blob_paths,
            )
        )


MIGRATIONS = [
    """
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE ingestion_runs (
        run_id VARCHAR PRIMARY KEY,
        started_at TIMESTAMP,
        finished_at TIMESTAMP,
        duration_seconds DOUBLE,
        total_sources_executed INTEGER,
        global_limit INTEGER,
        per_source_limit INTEGER
    );
    """,
    """
    CREATE TABLE source_runs (
        run_id VARCHAR,
        source_name VARCHAR,
        state VARCHAR,
        records_fetched INTEGER,
        records_valid INTEGER,
        PRIMARY KEY (run_id, source_name),
        FOREIGN KEY (run_id) REFERENCES ingestion_runs(run_id)
    );
    """,
    """
    CREATE TABLE raw_blobs (
        content_hash VARCHAR PRIMARY KEY,
        size_bytes INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE source_jobs (
        source_name VARCHAR,
        source_job_id VARCHAR,
        source_url VARCHAR,
        content_hash VARCHAR,
        first_seen_at TIMESTAMP,
        last_seen_at TIMESTAMP,
        missing_complete_runs INTEGER DEFAULT 0,
        status VARCHAR,
        PRIMARY KEY (source_name, source_job_id)
    );
    """,
    """
    CREATE TABLE source_job_observations (
        observation_id VARCHAR PRIMARY KEY,
        source_name VARCHAR,
        source_job_id VARCHAR,
        run_id VARCHAR,
        content_hash VARCHAR,
        observed_at TIMESTAMP,
        FOREIGN KEY (run_id) REFERENCES ingestion_runs(run_id),
        UNIQUE (run_id, source_name, source_job_id)
    );
    """,
    """
    ALTER TABLE source_job_observations ADD COLUMN source_url VARCHAR;
    """,
    """
    ALTER TABLE source_job_observations ADD COLUMN source_type VARCHAR;
    ALTER TABLE source_job_observations ADD COLUMN payload_media_type VARCHAR DEFAULT 'application/json';
    ALTER TABLE source_job_observations ADD COLUMN changed_since_previous BOOLEAN DEFAULT FALSE;
    """,
    """
    ALTER TABLE ingestion_runs ADD COLUMN application_version VARCHAR;
    """,
    """
    CREATE TABLE cleaned_source_text (
        cleaned_id VARCHAR PRIMARY KEY,
        observation_id VARCHAR,
        raw_content_hash VARCHAR,
        transformation_name VARCHAR,
        transformation_version VARCHAR,
        cleaned_text VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (observation_id) REFERENCES source_job_observations(observation_id),
        UNIQUE (observation_id, transformation_name, transformation_version)
    );
    """,
    """
    CREATE TABLE historical_quarantine (
        quarantine_id VARCHAR PRIMARY KEY,
        run_id VARCHAR,
        source_name VARCHAR,
        source_job_id VARCHAR,
        source_file VARCHAR,
        failure_phase VARCHAR,
        error_type VARCHAR,
        message VARCHAR,
        raw_content_hash VARCHAR,
        raw_payload VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    ALTER TABLE schema_migrations ADD COLUMN checksum VARCHAR;
    """,
]


class HistoricalStorage:
    def __init__(self, data_dir: Path, *, db_path: Path | None = None):
        self.data_dir = data_dir
        self.db_path = db_path or self.data_dir / "db" / "history.duckdb"
        self.blobs_dir = self.data_dir / "blobs" / "sha256"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.blobs_dir.mkdir(parents=True, exist_ok=True)

        self.conn = duckdb.connect(str(self.db_path))
        self._apply_migrations()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _apply_migrations(self) -> None:
        has_checksum_col = False
        applied_migrations: dict[int, str | None] = {}
        try:
            cols = [
                row[0]
                for row in self.conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'schema_migrations'"
                ).fetchall()
            ]
            has_checksum_col = "checksum" in cols
            if has_checksum_col:
                rows = self.conn.execute(
                    "SELECT version, checksum FROM schema_migrations ORDER BY version"
                ).fetchall()
                applied_migrations = {row[0]: row[1] for row in rows}
            else:
                rows = self.conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
                applied_migrations = {row[0]: None for row in rows}

            current_version = max(applied_migrations.keys()) if applied_migrations else -1
        except duckdb.CatalogException:
            current_version = -1

        if current_version >= len(MIGRATIONS):
            raise RuntimeError(
                f"Database schema version {current_version} is newer than supported "
                f"version {len(MIGRATIONS) - 1}"
            )

        # Migration tampering verification
        for ver, db_checksum in applied_migrations.items():
            if db_checksum is not None and ver < len(MIGRATIONS):
                code_sql = MIGRATIONS[ver].strip()
                code_checksum = hashlib.sha256(code_sql.encode("utf-8")).hexdigest()
                if db_checksum != code_checksum:
                    raise MigrationTamperedError(
                        f"Migration version {ver} has been modified! "
                        f"Applied checksum: {db_checksum}, Expected: {code_checksum}"
                    )

        for i, migration in enumerate(MIGRATIONS):
            sql_clean = migration.strip()
            migration_checksum = hashlib.sha256(sql_clean.encode("utf-8")).hexdigest()

            if i > current_version:
                logger.info(f"Applying migration version {i}")
                self.conn.execute("BEGIN TRANSACTION")
                try:
                    self.conn.execute(migration)
                    cols = [
                        row[0]
                        for row in self.conn.execute(
                            "SELECT column_name FROM information_schema.columns WHERE table_name = 'schema_migrations'"
                        ).fetchall()
                    ]
                    if "checksum" in cols:
                        self.conn.execute(
                            "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                            [i, migration_checksum],
                        )
                    else:
                        self.conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", [i])
                    self.conn.execute("COMMIT")
                except BaseException:
                    self.conn.execute("ROLLBACK")
                    raise
            elif has_checksum_col and applied_migrations.get(i) is None:
                self.conn.execute(
                    "UPDATE schema_migrations SET checksum = ? WHERE version = ?",
                    [migration_checksum, i],
                )

    def _get_blob_path(self, content_hash: str) -> Path:
        if not _SHA256_PATTERN.fullmatch(content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 hex digest")
        prefix1 = content_hash[:2]
        prefix2 = content_hash[2:4]
        return self.blobs_dir / prefix1 / prefix2 / f"{content_hash}.json"

    def write_blob(self, content_hash: str, payload_str: str) -> None:
        payload_bytes = payload_str.encode("utf-8")
        computed_hash = hashlib.sha256(payload_bytes).hexdigest()
        if content_hash != computed_hash:
            raise ValueError(f"Blob hash mismatch: expected {computed_hash}, got {content_hash}")

        blob_path = self._get_blob_path(content_hash)
        if blob_path.exists():
            if blob_path.read_bytes() != payload_bytes:
                raise ValueError(f"Existing blob does not match hash {content_hash}")
            self.conn.execute(
                """
                INSERT OR IGNORE INTO raw_blobs (content_hash, size_bytes)
                VALUES (?, ?)
                """,
                [content_hash, len(payload_bytes)],
            )
            return

        blob_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=blob_path.parent,
                prefix=f".{content_hash}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(payload_bytes)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temp_path = Path(temporary_file.name)
            os.link(temp_path, blob_path)
        except FileExistsError:
            if blob_path.read_bytes() != payload_bytes:
                raise ValueError(f"Concurrent blob does not match hash {content_hash}")
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

        self.conn.execute(
            """
            INSERT OR IGNORE INTO raw_blobs (content_hash, size_bytes)
            VALUES (?, ?)
            """,
            [content_hash, len(payload_bytes)],
        )

    def read_blob(self, content_hash: str) -> str:
        blob_path = self._get_blob_path(content_hash)
        payload = blob_path.read_text(encoding="utf-8")
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != content_hash:
            raise ValueError(f"Stored blob failed integrity check: {content_hash}")
        return payload

    def save_cleaned_text(self, cleaned: CleanedSourceText) -> None:
        self.conn.execute(
            """
            INSERT INTO cleaned_source_text (
                cleaned_id, observation_id, raw_content_hash,
                transformation_name, transformation_version, cleaned_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (observation_id, transformation_name, transformation_version) DO UPDATE
            SET cleaned_text = EXCLUDED.cleaned_text, created_at = EXCLUDED.created_at
            """,
            [
                cleaned.cleaned_id,
                cleaned.observation_id,
                cleaned.raw_content_hash,
                cleaned.transformation_name,
                cleaned.transformation_version,
                cleaned.cleaned_text,
                cleaned.created_at.isoformat(),
            ],
        )

    def get_cleaned_text(self, observation_id: str) -> CleanedSourceText | None:
        row = self.conn.execute(
            """
            SELECT cleaned_id, observation_id, raw_content_hash, transformation_name,
                   transformation_version, cleaned_text, created_at
            FROM cleaned_source_text
            WHERE observation_id = ?
            """,
            [observation_id],
        ).fetchone()
        if not row:
            return None
        return CleanedSourceText(
            cleaned_id=row[0],
            observation_id=row[1],
            raw_content_hash=row[2],
            transformation_name=row[3],
            transformation_version=row[4],
            cleaned_text=row[5],
            created_at=row[6],
        )

    def quarantine_record(self, record: HistoricalQuarantineRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO historical_quarantine (
                quarantine_id, run_id, source_name, source_job_id, source_file,
                failure_phase, error_type, message, raw_content_hash, raw_payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.quarantine_id,
                record.run_id,
                record.source_name,
                record.source_job_id,
                record.source_file,
                record.failure_phase,
                record.error_type,
                record.message,
                record.raw_content_hash,
                record.raw_payload,
                record.timestamp.isoformat(),
            ],
        )

    def get_quarantined_records(
        self, run_id: str | None = None
    ) -> list[HistoricalQuarantineRecord]:
        if run_id:
            rows = self.conn.execute(
                """
                SELECT quarantine_id, run_id, source_name, source_job_id, source_file,
                       failure_phase, error_type, message, raw_content_hash, raw_payload, created_at
                FROM historical_quarantine WHERE run_id = ? ORDER BY created_at
                """,
                [run_id],
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT quarantine_id, run_id, source_name, source_job_id, source_file,
                       failure_phase, error_type, message, raw_content_hash, raw_payload, created_at
                FROM historical_quarantine ORDER BY created_at
                """
            ).fetchall()

        return [
            HistoricalQuarantineRecord(
                quarantine_id=r[0],
                run_id=r[1],
                source_name=r[2],
                source_job_id=r[3],
                source_file=r[4],
                failure_phase=r[5],
                error_type=r[6],
                message=r[7],
                raw_content_hash=r[8],
                raw_payload=r[9],
                timestamp=r[10],
            )
            for r in rows
        ]

    def verify_integrity(self) -> IntegrityReport:
        database_hashes = {
            row[0] for row in self.conn.execute("SELECT content_hash FROM raw_blobs").fetchall()
        }
        observation_hashes = {
            row[0]
            for row in self.conn.execute(
                "SELECT DISTINCT content_hash FROM source_job_observations"
            ).fetchall()
        }

        missing_files: list[str] = []
        corrupt_files: list[str] = []
        for content_hash in sorted(database_hashes):
            blob_path = self._get_blob_path(content_hash)
            if not blob_path.is_file():
                missing_files.append(content_hash)
                continue
            if hashlib.sha256(blob_path.read_bytes()).hexdigest() != content_hash:
                corrupt_files.append(content_hash)

        filesystem_hashes: set[str] = set()
        invalid_blob_paths: list[str] = []
        if self.blobs_dir.exists():
            for blob_path in self.blobs_dir.rglob("*.json"):
                content_hash = blob_path.stem
                if not _SHA256_PATTERN.fullmatch(content_hash) or blob_path != self._get_blob_path(
                    content_hash
                ):
                    invalid_blob_paths.append(str(blob_path.relative_to(self.blobs_dir)))
                    continue
                filesystem_hashes.add(content_hash)

        return IntegrityReport(
            total_database_blobs=len(database_hashes),
            missing_files=tuple(missing_files),
            corrupt_files=tuple(corrupt_files),
            missing_metadata=tuple(sorted(observation_hashes - database_hashes)),
            orphan_database_blobs=tuple(sorted(database_hashes - observation_hashes)),
            orphan_files=tuple(sorted(filesystem_hashes - database_hashes)),
            invalid_blob_paths=tuple(sorted(invalid_blob_paths)),
        )

    def import_run(
        self, manifest: RunManifest, records: list[RawJobRecord], missing_runs_threshold: int = 3
    ) -> None:
        summary = manifest.summary
        if missing_runs_threshold <= 0:
            raise ValueError("missing_runs_threshold must be a positive integer")
        seen_record_keys: set[tuple[str, str]] = set()
        for record in records:
            if record.source_name not in summary.sources:
                raise ValueError(
                    f"Record source {record.source_name!r} is not present in the run manifest"
                )
            record_key = (record.source_name, record.source_job_id)
            if record_key in seen_record_keys:
                raise ValueError(
                    f"Duplicate record identity in run: {record.source_name}/{record.source_job_id}"
                )
            seen_record_keys.add(record_key)

        res = self.conn.execute(
            "SELECT run_id FROM ingestion_runs WHERE run_id = ?", [summary.run_id]
        ).fetchone()
        if res:
            logger.info(f"Run {summary.run_id} already imported. Skipping.")
            return

        self.conn.execute("BEGIN TRANSACTION")
        try:
            cursor = self.conn
            cursor.execute(
                """
                INSERT INTO ingestion_runs (
                    run_id, started_at, finished_at, duration_seconds,
                    total_sources_executed, global_limit, per_source_limit, application_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    summary.run_id,
                    summary.started_at.isoformat(),
                    summary.finished_at.isoformat(),
                    summary.duration_seconds,
                    summary.total_sources_executed,
                    summary.global_limit,
                    summary.per_source_limit,
                    summary.version,
                ],
            )

            for src_name, src_summary in summary.sources.items():
                cursor.execute(
                    """
                    INSERT INTO source_runs (
                        run_id, source_name, state, records_fetched, records_valid
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        summary.run_id,
                        src_summary.source_name,
                        src_summary.state.value,
                        src_summary.records_fetched,
                        src_summary.records_valid,
                    ],
                )

            observed_jobs = {src_name: set() for src_name in summary.sources}

            existing_jobs = {}
            if records:
                source_names = sorted({record.source_name for record in records})
                placeholders = ",".join(["?"] * len(source_names))
                rows = cursor.execute(
                    f"SELECT source_name, source_job_id, status, content_hash FROM source_jobs WHERE source_name IN ({placeholders})",
                    source_names,
                ).fetchall()
                for sn, sjid, st, ch in rows:
                    existing_jobs[(sn, sjid)] = (st, ch)

            obs_batch = []
            jobs_insert_batch = []
            jobs_update_batch = []

            for record in records:
                self.write_blob(record.content_hash, record.raw_payload)

                obs_id = str(uuid.uuid4())
                observed_at = record.collected_at.isoformat()

                existing = existing_jobs.get((record.source_name, record.source_job_id))
                changed_since_previous = False

                if not existing:
                    jobs_insert_batch.append(
                        [
                            record.source_name,
                            record.source_job_id,
                            record.source_url,
                            record.content_hash,
                            observed_at,
                            observed_at,
                            0,
                            "active",
                        ]
                    )
                    changed_since_previous = False
                else:
                    old_status, old_hash = existing
                    new_status = (
                        "reopened" if old_status in ("possibly_inactive", "closed") else "active"
                    )
                    changed_since_previous = old_hash != record.content_hash

                    jobs_update_batch.append(
                        [
                            record.source_url,
                            record.content_hash,
                            observed_at,
                            new_status,
                            record.source_name,
                            record.source_job_id,
                        ]
                    )

                source_type_val = record.source_type.value if record.source_type else None
                try:
                    json.loads(record.raw_payload)
                    payload_media_type = "application/json"
                except (TypeError, ValueError):
                    payload_media_type = "text/plain"

                obs_batch.append(
                    [
                        obs_id,
                        record.source_name,
                        record.source_job_id,
                        summary.run_id,
                        record.content_hash,
                        observed_at,
                        record.source_url,
                        source_type_val,
                        payload_media_type,
                        changed_since_previous,
                    ]
                )

                observed_jobs[record.source_name].add(record.source_job_id)

            if jobs_insert_batch:
                cursor.executemany(
                    """
                    INSERT INTO source_jobs (
                        source_name, source_job_id, source_url, content_hash,
                        first_seen_at, last_seen_at, missing_complete_runs, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    jobs_insert_batch,
                )

            if jobs_update_batch:
                cursor.executemany(
                    """
                    UPDATE source_jobs
                    SET source_url = ?, content_hash = ?, last_seen_at = ?, missing_complete_runs = 0, status = ?
                    WHERE source_name = ? AND source_job_id = ?
                    """,
                    jobs_update_batch,
                )

            if obs_batch:
                cursor.executemany(
                    """
                    INSERT INTO source_job_observations (
                        observation_id, source_name, source_job_id, run_id, content_hash,
                        observed_at, source_url, source_type, payload_media_type, changed_since_previous
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    obs_batch,
                )

            missing_updates = []
            for src_name, src_summary in summary.sources.items():
                if getattr(src_summary, "coverage_complete", False):
                    unseen = cursor.execute(
                        """
                        SELECT source_job_id, missing_complete_runs
                        FROM source_jobs
                        WHERE source_name = ? AND status IN ('active', 'possibly_inactive', 'reopened')
                        """,
                        [src_name],
                    ).fetchall()

                    for job_id, missing_count in unseen:
                        if job_id not in observed_jobs[src_name]:
                            new_missing = missing_count + 1
                            if new_missing >= missing_runs_threshold:
                                new_status = "closed"
                            else:
                                new_status = "possibly_inactive"

                            missing_updates.append([new_missing, new_status, src_name, job_id])

            if missing_updates:
                cursor.executemany(
                    """
                    UPDATE source_jobs
                    SET missing_complete_runs = ?, status = ?
                    WHERE source_name = ? AND source_job_id = ?
                    """,
                    missing_updates,
                )

            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def backup(self, destination_dir: Path) -> BackupManifest:
        destination_dir.mkdir(parents=True, exist_ok=True)
        backup_db_path = destination_dir / "history.duckdb"
        backup_blobs_dir = destination_dir / "blobs" / "sha256"

        self.conn.execute("CHECKPOINT")

        shutil.copy2(self.db_path, backup_db_path)

        if self.blobs_dir.exists():
            shutil.copytree(self.blobs_dir, backup_blobs_dir, dirs_exist_ok=True)

        db_bytes = backup_db_path.read_bytes()
        db_checksum = hashlib.sha256(db_bytes).hexdigest()

        total_blobs = 0
        total_bytes = 0
        if backup_blobs_dir.exists():
            for p in backup_blobs_dir.rglob("*.json"):
                if p.is_file():
                    total_blobs += 1
                    total_bytes += p.stat().st_size

        from radar_vagas import __version__

        current_version_num = len(MIGRATIONS) - 1

        manifest = BackupManifest(
            backup_id=f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
            created_at=datetime.now(UTC),
            application_version=__version__,
            schema_version=current_version_num,
            db_checksum=db_checksum,
            total_blobs=total_blobs,
            total_bytes=total_bytes,
        )

        manifest_path = destination_dir / "backup_manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

        logger.info(f"Created backup {manifest.backup_id} at {destination_dir}")
        return manifest

    @classmethod
    def restore(
        cls, backup_dir: Path, target_data_dir: Path, force: bool = False
    ) -> "HistoricalStorage":
        manifest_path = backup_dir / "backup_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Backup manifest not found in {backup_dir}")

        manifest = BackupManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

        target_db_path = target_data_dir / "db" / "history.duckdb"
        target_blobs_dir = target_data_dir / "blobs" / "sha256"

        if target_data_dir.exists() and any(target_data_dir.iterdir()) and not force:
            raise FileExistsError(
                f"Target data directory {target_data_dir} is not empty. Use force=True to overwrite."
            )

        target_data_dir.mkdir(parents=True, exist_ok=True)

        backup_db_path = backup_dir / "history.duckdb"
        target_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_db_path, target_db_path)

        restored_db_checksum = hashlib.sha256(target_db_path.read_bytes()).hexdigest()
        if restored_db_checksum != manifest.db_checksum:
            raise ValueError("Restored database checksum mismatch!")

        backup_blobs_dir = backup_dir / "blobs" / "sha256"
        if backup_blobs_dir.exists():
            shutil.copytree(backup_blobs_dir, target_blobs_dir, dirs_exist_ok=True)

        storage = cls(target_data_dir, db_path=target_db_path)
        report = storage.verify_integrity()
        if not report.is_valid:
            raise ValueError(f"Restored storage failed integrity check: {report}")

        logger.info(f"Successfully restored backup {manifest.backup_id} to {target_data_dir}")
        return storage

    def prune_retention(self, policy: RetentionPolicy, force: bool = False) -> RetentionReport:
        if not policy.active and not force:
            logger.info("Retention policy inactive. Returning empty report.")
            return RetentionReport(preview_only=True)

        preview_only = not force

        cutoff_str = None
        if policy.max_age_days is not None:
            cutoff_dt = datetime.now(UTC) - timedelta(days=policy.max_age_days)
            cutoff_str = cutoff_dt.isoformat()

        total_runs = self.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
        if total_runs <= policy.keep_minimum_runs:
            logger.info(
                f"Total runs ({total_runs}) <= keep_minimum_runs ({policy.keep_minimum_runs}). Nothing to prune."
            )
            return RetentionReport(preview_only=preview_only)

        all_runs = self.conn.execute(
            "SELECT run_id, finished_at FROM ingestion_runs ORDER BY finished_at ASC, run_id ASC"
        ).fetchall()

        eligible_runs = all_runs[: -policy.keep_minimum_runs]
        if cutoff_str:
            eligible_runs = [r for r in eligible_runs if r[1] and str(r[1]) < cutoff_str]

        if not eligible_runs:
            return RetentionReport(preview_only=preview_only)

        eligible_run_ids = [r[0] for r in eligible_runs]
        placeholders = ",".join(["?"] * len(eligible_run_ids))

        obs_to_delete = self.conn.execute(
            f"SELECT observation_id, content_hash FROM source_job_observations WHERE run_id IN ({placeholders})",
            eligible_run_ids,
        ).fetchall()

        obs_count = len(obs_to_delete)
        obs_hashes = {r[1] for r in obs_to_delete}

        remaining_hashes = {
            r[0]
            for r in self.conn.execute(
                f"SELECT DISTINCT content_hash FROM source_job_observations WHERE run_id NOT IN ({placeholders})",
                eligible_run_ids,
            ).fetchall()
        }

        orphan_blobs_to_delete = obs_hashes - remaining_hashes

        freed_bytes = 0
        pruned_blobs_count = 0
        for h in orphan_blobs_to_delete:
            blob_path = self._get_blob_path(h)
            if blob_path.exists():
                freed_bytes += blob_path.stat().st_size
                pruned_blobs_count += 1

        if not preview_only:
            # 1. Delete child table records (observations, cleaned_text, source_runs, quarantine)
            self.conn.execute("BEGIN TRANSACTION")
            try:
                self.conn.execute(
                    f"DELETE FROM historical_quarantine WHERE run_id IN ({placeholders})",
                    eligible_run_ids,
                )
                self.conn.execute(
                    f"DELETE FROM cleaned_source_text WHERE observation_id IN (SELECT observation_id FROM source_job_observations WHERE run_id IN ({placeholders}))",
                    eligible_run_ids,
                )
                self.conn.execute(
                    f"DELETE FROM source_job_observations WHERE run_id IN ({placeholders})",
                    eligible_run_ids,
                )
                self.conn.execute(
                    f"DELETE FROM source_runs WHERE run_id IN ({placeholders})",
                    eligible_run_ids,
                )
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

            # 2. Delete parent ingestion_runs records
            self.conn.execute("BEGIN TRANSACTION")
            try:
                self.conn.execute(
                    f"DELETE FROM ingestion_runs WHERE run_id IN ({placeholders})",
                    eligible_run_ids,
                )
                for h in orphan_blobs_to_delete:
                    self.conn.execute("DELETE FROM raw_blobs WHERE content_hash = ?", [h])
                    blob_path = self._get_blob_path(h)
                    if blob_path.exists():
                        blob_path.unlink()
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

        return RetentionReport(
            preview_only=preview_only,
            pruned_runs=len(eligible_run_ids),
            pruned_observations=obs_count,
            pruned_blobs=pruned_blobs_count,
            freed_bytes=freed_bytes,
            recoverable=False,
        )

    def close(self) -> None:
        self.conn.close()
