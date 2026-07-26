"""Unit tests for historical quarantine."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from radar_vagas.domain.models import HistoricalQuarantineRecord
from radar_vagas.infrastructure.history import HistoricalStorage


def test_quarantine_record_persistence_and_retrieval(tmp_path: Path):
    storage = HistoricalStorage(tmp_path / "data")

    q_rec = HistoricalQuarantineRecord(
        quarantine_id="quar_1",
        run_id="run_q_1",
        source_name="src_q",
        source_job_id="job_q",
        source_file="src_q-job_q.json",
        failure_phase="import_parse",
        error_type="ValueError",
        message="Invalid JSON payload",
        raw_payload="invalid json content",
        timestamp=datetime.now(UTC),
    )

    storage.quarantine_record(q_rec)

    quarantined = storage.get_quarantined_records(run_id="run_q_1")
    assert len(quarantined) == 1
    assert quarantined[0].quarantine_id == "quar_1"
    assert quarantined[0].error_type == "ValueError"
    assert quarantined[0].raw_payload == "invalid json content"

    storage.close()


def test_import_quarantine_records_raw_payload_hash(tmp_path: Path):
    from radar_vagas.core.history_service import HistoryService
    from radar_vagas.domain.models import (
        IngestionSummary,
        RunManifest,
        RunState,
        SourceRunSummary,
    )
    from radar_vagas.infrastructure.storage import LocalStorage

    local = LocalStorage(tmp_path / "local")
    run_dir = local.runs_dir / "broken-run"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    manifest = RunManifest(
        summary=IngestionSummary(
            run_id="broken-run",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            version="0.1.0",
            total_sources_requested=1,
            total_sources_executed=1,
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_q": SourceRunSummary(
                    source_name="src_q",
                    state=RunState.success,
                    records_fetched=1,
                    records_valid=1,
                )
            },
        )
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    malformed = "{not-json"
    (raw_dir / "src_q-job-1.json").write_text(malformed, encoding="utf-8")

    history = HistoricalStorage(tmp_path / "history")
    report = HistoryService(local, history).import_all_runs()
    quarantined = history.get_quarantined_records("broken-run")

    assert report.failed_runs == 1
    assert quarantined[0].raw_content_hash == hashlib.sha256(malformed.encode()).hexdigest()
    history.close()
