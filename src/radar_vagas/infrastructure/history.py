import hashlib
import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import duckdb

from radar_vagas.domain.models import RawJobRecord, RunManifest

logger = logging.getLogger(__name__)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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

    def _apply_migrations(self) -> None:
        try:
            self.conn.execute("SELECT MAX(version) FROM schema_migrations")
            current_version = self.conn.fetchone()[0]
            if current_version is None:
                current_version = -1
        except duckdb.CatalogException:
            current_version = -1

        if current_version >= len(MIGRATIONS):
            raise RuntimeError(
                f"Database schema version {current_version} is newer than supported "
                f"version {len(MIGRATIONS) - 1}"
            )

        for i, migration in enumerate(MIGRATIONS):
            if i > current_version:
                logger.info(f"Applying migration version {i}")
                self.conn.execute("BEGIN TRANSACTION")
                try:
                    self.conn.execute(migration)
                    if i > 0:
                        self.conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", [i])
                    else:
                        self.conn.execute("INSERT INTO schema_migrations (version) VALUES (0)")
                    self.conn.execute("COMMIT")
                except BaseException:
                    self.conn.execute("ROLLBACK")
                    raise

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

        # Check idempotency
        res = self.conn.execute(
            "SELECT run_id FROM ingestion_runs WHERE run_id = ?", [summary.run_id]
        ).fetchone()
        if res:
            logger.info(f"Run {summary.run_id} already imported. Skipping.")
            return

        # Keep the complete database mutation atomic. CAS files written before
        # a rollback are harmless unreferenced blobs and may be reused later.
        self.conn.execute("BEGIN TRANSACTION")
        try:
            cursor = self.conn
            # 1. Insert Run
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

            # 2. Insert Source Runs
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

            # 3. Process Records
            observed_jobs = {src_name: set() for src_name in summary.sources}

            # Pre-fetch existing source jobs to calculate changed_since_previous and avoid individual selects
            existing_jobs = {}
            if records:
                source_names = sorted({record.source_name for record in records})
                # Using a single query to get all existing jobs for the relevant sources
                # We can construct an IN clause or just fetch all for those sources since they shouldn't be millions per run yet.
                # A better approach is to use a temp table or just fetch them.
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
                # Write CAS blob (This has its own IGNORE logic which is fine to keep per-record for now,
                # as it renames files on disk)
                self.write_blob(record.content_hash, record.raw_payload)

                obs_id = str(uuid.uuid4())
                observed_at = record.collected_at.isoformat()

                existing = existing_jobs.get((record.source_name, record.source_job_id))
                changed_since_previous = False

                if not existing:
                    # New job
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
                    # Existing job
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

            # 4. Handle Missing Coverage
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

    def close(self) -> None:
        self.conn.close()
