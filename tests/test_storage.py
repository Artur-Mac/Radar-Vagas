"""Unit tests for LocalStorage infrastructure."""

import json
from datetime import UTC, datetime
from pathlib import Path

from radar_vagas.domain.models import (
    IngestionSummary,
    RejectedRecord,
    RunManifest,
)
from radar_vagas.infrastructure.storage import LocalStorage


def test_ensure_run_dirs(tmp_path: Path) -> None:
    """Test ensuring run directory structure creation."""
    storage = LocalStorage(tmp_path)
    run_id = "run_20240101_120000_abc12345"

    storage.ensure_run_dirs(run_id)

    run_dir = tmp_path / "runs" / run_id
    assert run_dir.is_dir()
    assert (run_dir / "raw").is_dir()
    assert (run_dir / "quarantine").is_dir()


def test_save_raw_record_content_and_safe_filename(tmp_path: Path) -> None:
    """Test saving raw record with safe filename sanitization and accurate payload content."""
    storage = LocalStorage(tmp_path)
    run_id = "run_test_raw"
    storage.ensure_run_dirs(run_id)

    payload = '{"id": "job/123", "title": "Data Engineer"}'

    # Test sanitization of slashes and backslashes in source_name and source_job_id
    storage.save_raw_record(
        run_id=run_id,
        source_name="company/team\\source",
        source_job_id="dev/job\\456",
        payload=payload,
    )

    expected_filename = "company_team_source-dev_job_456.json"
    file_path = tmp_path / "runs" / run_id / "raw" / expected_filename

    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == payload


def test_save_quarantined_record(tmp_path: Path) -> None:
    """Test saving quarantined records with normal, missing ID, and None payloads."""
    storage = LocalStorage(tmp_path)
    run_id = "run_test_quarantine"
    storage.ensure_run_dirs(run_id)

    # 1. Normal record with slashes
    payload1 = '{"corrupted": true}'
    storage.save_quarantined_record(
        run_id=run_id,
        source_name="src/1",
        source_job_id="job/q1",
        payload=payload1,
    )
    file1 = tmp_path / "runs" / run_id / "quarantine" / "src_1-job_q1.json"
    assert file1.exists()
    assert file1.read_text(encoding="utf-8") == payload1

    # 2. Record with None source_job_id and None payload
    storage.save_quarantined_record(
        run_id=run_id,
        source_name="src_unk",
        source_job_id=None,
        payload=None,
    )
    file2 = tmp_path / "runs" / run_id / "quarantine" / "src_unk-unknown_id.json"
    assert file2.exists()
    assert file2.read_text(encoding="utf-8") == "{}"


def test_save_manifest(tmp_path: Path) -> None:
    """Test saving run manifest and summary files."""
    storage = LocalStorage(tmp_path)
    run_id = "run_test_manifest"
    storage.ensure_run_dirs(run_id)

    now = datetime.now(UTC)
    summary = IngestionSummary(
        run_id=run_id,
        started_at=now,
        finished_at=now,
        version="0.1.0",
        total_sources_requested=1,
        total_sources_executed=1,
        global_limit=10,
        per_source_limit=5,
        total_fetched=2,
        total_valid=1,
        total_rejected=1,
    )
    manifest = RunManifest(
        summary=summary,
        rejected=[RejectedRecord(source_name="test_src", source_job_id="j1", reason="invalid")],
        quarantined=[],
        duplicates=[],
    )

    storage.save_manifest(run_id, manifest)

    manifest_file = tmp_path / "runs" / run_id / "manifest.json"
    summary_file = tmp_path / "runs" / run_id / "summary.json"

    assert manifest_file.exists()
    assert summary_file.exists()

    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    summary_data = json.loads(summary_file.read_text(encoding="utf-8"))

    assert manifest_data["summary"]["run_id"] == run_id
    assert manifest_data["rejected"][0]["source_job_id"] == "j1"
    assert summary_data["run_id"] == run_id
    assert summary_data["total_fetched"] == 2
