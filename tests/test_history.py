import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from radar_vagas.domain.models import (
    IngestionSummary,
    NormalizedJobLink,
    RawJobRecord,
    RunManifest,
    RunState,
    SourceRunSummary,
)
from radar_vagas.infrastructure.history import HistoricalStorage


@pytest.fixture
def history(tmp_path: Path):
    storage = HistoricalStorage(tmp_path)
    yield storage
    storage.close()


def test_migrations_create_tables(history: HistoricalStorage):
    tables = [row[0] for row in history.conn.execute("SHOW TABLES").fetchall()]
    assert "schema_migrations" in tables
    assert "ingestion_runs" in tables
    assert "source_runs" in tables
    assert "raw_blobs" in tables
    assert "source_jobs" in tables
    assert "source_job_observations" in tables


def test_write_and_read_blob(history: HistoricalStorage):
    payload = json.dumps({"test": "data"}, sort_keys=True)
    content_hash = hashlib.sha256(payload.encode()).hexdigest()

    history.write_blob(content_hash, payload)

    # Verify in CAS directory
    blob_path = history._get_blob_path(content_hash)
    assert blob_path.exists()
    assert history.read_blob(content_hash) == payload

    # Verify in DuckDB
    res = history.conn.execute(
        "SELECT size_bytes FROM raw_blobs WHERE content_hash = ?", [content_hash]
    ).fetchone()
    assert res is not None
    assert res[0] == len(payload.encode())


def test_blob_rejects_invalid_path_and_hash(history: HistoricalStorage):
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        history.read_blob("../../outside")

    with pytest.raises(ValueError, match="Blob hash mismatch"):
        history.write_blob("0" * 64, '{"different":true}')


def test_integrity_report_detects_corrupt_and_orphan_files(history: HistoricalStorage):
    payload = '{"title":"Data Engineer"}'
    content_hash = hashlib.sha256(payload.encode()).hexdigest()
    history.write_blob(content_hash, payload)

    healthy_report = history.verify_integrity()
    assert healthy_report.orphan_database_blobs == (content_hash,)

    history._get_blob_path(content_hash).write_text("corrupt", encoding="utf-8")
    orphan_hash = hashlib.sha256(b"orphan").hexdigest()
    orphan_path = history._get_blob_path(orphan_hash)
    orphan_path.parent.mkdir(parents=True)
    orphan_path.write_text("orphan", encoding="utf-8")

    report = history.verify_integrity()

    assert report.is_valid is False
    assert report.corrupt_files == (content_hash,)
    assert report.orphan_files == (orphan_hash,)


def test_explicit_database_path(tmp_path: Path):
    database_path = tmp_path / "custom" / "career-history.duckdb"
    storage = HistoricalStorage(tmp_path / "data", db_path=database_path)
    try:
        assert storage.db_path == database_path
        assert database_path.exists()
    finally:
        storage.close()


def test_import_manifest_idempotency(history: HistoricalStorage):
    manifest = RunManifest(
        summary=IngestionSummary(
            run_id="test_run_1",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_seconds=1.5,
            total_sources_requested=1,
            total_sources_executed=1,
            version="0.1.0",
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_a": SourceRunSummary(
                    source_name="src_a",
                    state=RunState.success,
                    records_fetched=10,
                    records_valid=10,
                )
            },
        )
    )
    history.import_run(manifest, [])

    # Should insert exactly 1 row
    runs = history.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
    assert runs == 1

    # Calling again should not duplicate
    history.import_run(manifest, [])
    runs = history.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
    assert runs == 1


def test_import_manifest_records_observations(history: HistoricalStorage):
    rec1 = RawJobRecord(
        source_name="src_a",
        source_job_id="job_1",
        raw_payload="Payload 1",
        source_url="http://a/1",
        content_hash="5b4a9646a2f29587a8753dbd85691301d7010595e44c0a910d9cb2ae20ad132a",
    )

    manifest = RunManifest(
        summary=IngestionSummary(
            run_id="run_2",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_seconds=1.5,
            total_sources_requested=1,
            total_sources_executed=1,
            version="0.1.0",
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_a": SourceRunSummary(
                    source_name="src_a",
                    state=RunState.success,
                    records_fetched=1,
                    records_valid=1,
                    coverage_complete=True,
                )
            },
        )
    )

    history.import_run(manifest, [rec1])

    # Verify Blob
    blob = history.read_blob("5b4a9646a2f29587a8753dbd85691301d7010595e44c0a910d9cb2ae20ad132a")
    assert blob == "Payload 1"

    # Verify Observation
    obs = history.conn.execute(
        "SELECT source_name, source_job_id, run_id, content_hash FROM source_job_observations"
    ).fetchall()
    assert len(obs) == 1
    assert obs[0] == (
        "src_a",
        "job_1",
        "run_2",
        "5b4a9646a2f29587a8753dbd85691301d7010595e44c0a910d9cb2ae20ad132a",
    )
    media_type, changed = history.conn.execute(
        """
        SELECT payload_media_type, changed_since_previous
        FROM source_job_observations
        WHERE run_id = 'run_2'
        """
    ).fetchone()
    assert media_type == "text/plain"
    assert changed is False

    # Verify Source Job
    job = history.conn.execute(
        "SELECT status, missing_complete_runs FROM source_jobs WHERE source_job_id = 'job_1'"
    ).fetchone()
    assert job is not None
    assert job[0] == "active"
    assert job[1] == 0

    observation_id = history.conn.execute(
        "SELECT observation_id FROM source_job_observations WHERE run_id = 'run_2'"
    ).fetchone()[0]
    link = NormalizedJobLink(
        normalized_job_id="normalized-job-1",
        source_name="src_a",
        source_job_id="job_1",
        observation_id=observation_id,
        raw_content_hash=rec1.content_hash,
    )
    history.save_normalized_job_link(link)
    stored_link = history.get_normalized_job_links("normalized-job-1")[0]
    assert stored_link.normalized_job_id == link.normalized_job_id
    assert stored_link.observation_id == observation_id
    assert stored_link.raw_content_hash == rec1.content_hash

    with pytest.raises(ValueError, match="provenance"):
        history.save_normalized_job_link(link.model_copy(update={"raw_content_hash": "0" * 64}))

    with pytest.raises(ValueError, match="cleaned artifact"):
        history.save_normalized_job_link(
            link.model_copy(update={"cleaned_id": "missing-cleaned-id"})
        )


def test_import_run_is_atomic(history: HistoricalStorage):
    record = RawJobRecord(
        source_name="src_a",
        source_job_id="job_1",
        raw_payload='{"title":"Data Engineer"}',
        source_url="https://example.com/jobs/1",
    )
    manifest = RunManifest(
        summary=IngestionSummary(
            run_id="atomic_run",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_seconds=0.0,
            total_sources_requested=1,
            total_sources_executed=1,
            version="0.1.0",
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_a": SourceRunSummary(
                    source_name="src_a",
                    state=RunState.success,
                    records_fetched=2,
                    records_valid=2,
                )
            },
        )
    )

    with pytest.raises(ValueError, match="Duplicate record identity"):
        history.import_run(manifest, [record, record])

    assert (
        history.conn.execute(
            "SELECT COUNT(*) FROM ingestion_runs WHERE run_id = 'atomic_run'"
        ).fetchone()[0]
        == 0
    )


def test_missing_complete_runs_logic(history: HistoricalStorage):
    # Setup initial job
    rec1 = RawJobRecord(
        source_name="src_a",
        source_job_id="job_1",
        raw_payload="Payload 1",
        source_url="http://a/1",
        content_hash="5b4a9646a2f29587a8753dbd85691301d7010595e44c0a910d9cb2ae20ad132a",
    )

    manifest1 = RunManifest(
        summary=IngestionSummary(
            run_id="run_1",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_seconds=1.0,
            total_sources_requested=1,
            total_sources_executed=1,
            version="0.1.0",
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_a": SourceRunSummary(
                    source_name="src_a",
                    state=RunState.success,
                    records_fetched=1,
                    records_valid=1,
                    coverage_complete=True,
                )
            },
        )
    )
    history.import_run(manifest1, [rec1])

    # Run 2: job_1 is NOT in the run, and coverage_complete=True
    manifest2 = RunManifest(
        summary=IngestionSummary(
            run_id="run_2",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_seconds=1.0,
            total_sources_requested=1,
            total_sources_executed=1,
            version="0.1.0",
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_a": SourceRunSummary(
                    source_name="src_a",
                    state=RunState.success,
                    records_fetched=0,
                    records_valid=0,
                    coverage_complete=True,
                )
            },
        )
    )
    history.import_run(manifest2, [])

    job = history.conn.execute(
        "SELECT status, missing_complete_runs FROM source_jobs WHERE source_job_id = 'job_1'"
    ).fetchone()
    assert job[1] == 1
    assert job[0] == "possibly_inactive"

    # Import again twice to reach missing = 3
    manifest3 = manifest2.model_copy(deep=True)
    manifest3.summary.run_id = "run_3"
    history.import_run(manifest3, [])

    manifest4 = manifest2.model_copy(deep=True)
    manifest4.summary.run_id = "run_4"
    history.import_run(manifest4, [])

    job = history.conn.execute(
        "SELECT status, missing_complete_runs FROM source_jobs WHERE source_job_id = 'job_1'"
    ).fetchone()
    assert job[1] == 3
    assert job[0] == "closed"

    # Run 5: job_1 returns!
    manifest5 = manifest1.model_copy(deep=True)
    manifest5.summary.run_id = "run_5"
    history.import_run(manifest5, [rec1])

    job = history.conn.execute(
        "SELECT status, missing_complete_runs FROM source_jobs WHERE source_job_id = 'job_1'"
    ).fetchone()
    assert job[1] == 0
    assert job[0] == "reopened"
