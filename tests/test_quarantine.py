"""Unit tests for historical quarantine."""

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
