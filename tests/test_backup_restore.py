"""Round-trip tests for backup and restore functionality."""

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
def sample_history(tmp_path: Path) -> HistoricalStorage:
    data_dir = tmp_path / "original_data"
    storage = HistoricalStorage(data_dir)

    record = RawJobRecord(
        source_name="src_backup",
        source_job_id="job_b1",
        source_url="http://example.com/b1",
        raw_payload='{"title": "Backup Job", "description": "<p>Sample content</p>"}',
        collected_at=datetime.now(UTC),
    )

    manifest = RunManifest(
        summary=IngestionSummary(
            run_id="run_backup_1",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            version="0.1.0",
            total_sources_requested=1,
            total_sources_executed=1,
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_backup": SourceRunSummary(
                    source_name="src_backup",
                    state=RunState.success,
                    records_fetched=1,
                    records_valid=1,
                    coverage_complete=True,
                )
            },
        )
    )

    storage.import_run(manifest, [record])
    return storage


def test_backup_and_restore_round_trip(sample_history: HistoricalStorage, tmp_path: Path):
    backup_dir = tmp_path / "backups" / "backup_1"

    manifest = sample_history.backup(backup_dir)

    assert manifest.backup_id.startswith("backup_")
    assert manifest.total_blobs == 1
    assert (backup_dir / "history.duckdb").exists()
    assert (backup_dir / "backup_manifest.json").exists()

    target_data_dir = tmp_path / "restored_data"
    restored_storage = HistoryService.restore(backup_dir, target_data_dir)

    report = restored_storage.verify_integrity()
    assert report.is_valid

    # Replay records from restored storage
    service = HistoryService(LocalStorage(tmp_path), restored_storage)
    records = service.get_run_records("run_backup_1")
    assert len(records) == 1
    assert records[0].source_job_id == "job_b1"
    assert "Backup Job" in records[0].raw_payload

    restored_storage.close()


def test_restore_fails_if_target_exists_without_force(
    sample_history: HistoricalStorage, tmp_path: Path
):
    backup_dir = tmp_path / "backups" / "backup_2"
    sample_history.backup(backup_dir)

    target_data_dir = tmp_path / "non_empty_target"
    target_data_dir.mkdir(parents=True)
    (target_data_dir / "some_file.txt").write_text("existing content")

    with pytest.raises(FileExistsError, match="is not empty"):
        HistoryService.restore(backup_dir, target_data_dir, force=False)

    # Works with force=True
    restored = HistoryService.restore(backup_dir, target_data_dir, force=True)
    assert restored.verify_integrity().is_valid
    restored.close()
    assert not (target_data_dir / "some_file.txt").exists()


def test_backup_refuses_to_merge_into_existing_destination(
    sample_history: HistoricalStorage, tmp_path: Path
):
    backup_dir = tmp_path / "existing_backup"
    backup_dir.mkdir()
    (backup_dir / "keep.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        sample_history.backup(backup_dir)

    assert (backup_dir / "keep.txt").read_text(encoding="utf-8") == "do not overwrite"
