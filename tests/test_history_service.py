from datetime import UTC, datetime
from pathlib import Path

import pytest

from radar_vagas.core.history_service import HistoryService
from radar_vagas.domain.models import (
    IngestionSummary,
    RawJobRecord,
    RunManifest,
    RunState,
    SourceRunSummary,
)
from radar_vagas.infrastructure.history import HistoricalStorage
from radar_vagas.infrastructure.storage import LocalStorage


@pytest.fixture
def storage(tmp_path: Path):
    return LocalStorage(tmp_path / "runs")


@pytest.fixture
def history(tmp_path: Path):
    storage = HistoricalStorage(tmp_path / "history")
    yield storage
    storage.close()


@pytest.fixture
def service(storage: LocalStorage, history: HistoricalStorage):
    return HistoryService(storage, history)


def test_import_all_runs(
    service: HistoryService, storage: LocalStorage, history: HistoricalStorage
):
    run_id = "test_run_123"
    storage.runs_dir.mkdir(parents=True, exist_ok=True)
    run_dir = storage.runs_dir / run_id
    run_dir.mkdir()
    raw_dir = run_dir / "raw"
    raw_dir.mkdir()

    manifest = RunManifest(
        summary=IngestionSummary(
            run_id=run_id,
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
                    source_name="src_a", state=RunState.success, records_fetched=1, records_valid=1
                )
            },
        )
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json())

    rec1 = RawJobRecord(
        source_name="src_a", source_job_id="job_1", raw_payload="Payload 1", source_url="http://a/1"
    )
    # The record initialization recomputes content_hash.

    (raw_dir / "job_1.json").write_text(rec1.model_dump_json())

    # Run import
    count = service.import_all_runs()
    assert count == 1

    # Verify in duckdb
    runs = history.conn.execute("SELECT run_id FROM ingestion_runs").fetchall()
    assert len(runs) == 1
    assert runs[0][0] == run_id

    jobs = history.conn.execute(
        "SELECT source_name, source_job_id, source_url FROM source_jobs"
    ).fetchall()
    assert len(jobs) == 1
    assert jobs[0] == ("src_a", "job_1", "http://a/1")

    # Try import again, should return 0 (skipped)
    # Wait, the method import_all_runs doesn't strictly return 0 on skip, but it skips. Let's just check no duplication
    count2 = service.import_all_runs()
    assert count2 == 0  # we only count imported runs

    # Test replay
    records = service.get_run_records(run_id)
    assert len(records) == 1
    assert records[0].source_name == "src_a"
    assert records[0].source_job_id == "job_1"
    assert records[0].source_url == "http://a/1"
    assert records[0].raw_payload == "Payload 1"
    assert records[0].content_hash == rec1.content_hash


def test_imports_legacy_payload_only_run(
    service: HistoryService, storage: LocalStorage, history: HistoricalStorage
):
    """Época 3 runs stored raw payloads rather than RawJobRecord envelopes."""
    run_id = "legacy_run"
    run_dir = storage.runs_dir / run_id
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    manifest = RunManifest(
        summary=IngestionSummary(
            run_id=run_id,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            total_sources_requested=1,
            total_sources_executed=1,
            version="0.1.0",
            global_limit=None,
            per_source_limit=None,
            sources={
                "arbeitnow": SourceRunSummary(
                    source_name="arbeitnow",
                    state=RunState.success,
                    records_fetched=1,
                    records_valid=1,
                )
            },
        )
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    (raw_dir / "arbeitnow-job-123.json").write_text(
        '{"slug":"job-123","url":"https://example.com/jobs/123","title":"Data Engineer"}',
        encoding="utf-8",
    )

    assert service.import_all_runs() == 1
    records = service.get_run_records(run_id)
    assert len(records) == 1
    assert records[0].source_name == "arbeitnow"
    assert records[0].source_job_id == "job-123"
    assert records[0].source_url == "https://example.com/jobs/123"


def test_legacy_import_preserves_raw_payload_bytes(service: HistoryService, storage: LocalStorage):
    run_id = "legacy_exact_payload"
    raw_dir = storage.runs_dir / run_id / "raw"
    raw_dir.mkdir(parents=True)
    manifest = RunManifest(
        summary=IngestionSummary(
            run_id=run_id,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
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
                )
            },
        )
    )
    (storage.runs_dir / run_id / "manifest.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    original_payload = '{\n  "url": "https://example.com/jobs/1",\n  "title": "Data Engineer"\n}\n'
    (raw_dir / "src_a-job-1.json").write_text(original_payload, encoding="utf-8")

    assert service.import_all_runs() == 1
    assert service.get_run_records(run_id)[0].raw_payload == original_payload


def test_replay_uses_url_from_the_original_observation(
    service: HistoryService, history: HistoricalStorage
):
    base_summary = IngestionSummary(
        run_id="url_run_1",
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
                records_fetched=1,
                records_valid=1,
            )
        },
    )
    first = RawJobRecord(
        source_name="src_a",
        source_job_id="job-1",
        source_url="https://example.com/original",
        raw_payload='{"version":1}',
    )
    history.import_run(RunManifest(summary=base_summary), [first])

    second_summary = base_summary.model_copy(deep=True)
    second_summary.run_id = "url_run_2"
    second = RawJobRecord(
        source_name="src_a",
        source_job_id="job-1",
        source_url="https://example.com/updated",
        raw_payload='{"version":2}',
    )
    history.import_run(RunManifest(summary=second_summary), [second])

    replayed = service.get_run_records("url_run_1")
    assert replayed[0].source_url == "https://example.com/original"
    assert replayed[0].raw_payload == '{"version":1}'
