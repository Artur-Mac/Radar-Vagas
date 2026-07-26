from datetime import UTC, datetime
from pathlib import Path

import pytest

from radar_vagas.cli import main
from radar_vagas.domain.models import (
    IngestionSummary,
    RawJobRecord,
    RunManifest,
    RunState,
    SourceRunSummary,
)


@pytest.fixture
def run_dir(tmp_path: Path):
    run_id = "test_run_123"
    runs_dir = tmp_path / "data" / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
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
    (raw_dir / "job_1.json").write_text(rec1.model_dump_json())
    return tmp_path


def test_cli_history_import(run_dir: Path, capsys):
    db_path = run_dir / "db" / "history.duckdb"
    db_path.parent.mkdir()

    code = main(
        ["history", "import", "--output-dir", str(run_dir / "data"), "--db-path", str(db_path)]
    )
    assert code == 0

    captured = capsys.readouterr()
    assert "Importing runs from" in captured.out
    assert "IMPORT REPORT" in captured.out
    assert "Imported Runs:    1" in captured.out
    assert "Imported Records: 1" in captured.out


def test_cli_history_replay(run_dir: Path, capsys):
    db_path = run_dir / "db" / "history.duckdb"
    db_path.parent.mkdir(exist_ok=True)

    # Import first
    main(["history", "import", "--output-dir", str(run_dir / "data"), "--db-path", str(db_path)])

    # Replay
    code = main(["history", "replay", "test_run_123", "--db-path", str(db_path)])
    assert code == 0

    captured = capsys.readouterr()
    assert "REPLAY RESULTS" in captured.out
    assert "src_a" in captured.out
    assert "job_1" in captured.out
    assert "Total Records: 1" in captured.out


def test_cli_history_replay_not_found(run_dir: Path, capsys):
    db_path = run_dir / "db" / "history.duckdb"
    code = main(["history", "replay", "non_existent", "--db-path", str(db_path)])
    assert code == 1


def test_cli_history_init(run_dir: Path, capsys):
    db_path = run_dir / "db" / "history.duckdb"
    code = main(["history", "init", "--db-path", str(db_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "Historical storage initialized" in captured.out


def test_cli_history_stats(run_dir: Path, capsys):
    db_path = run_dir / "db" / "history.duckdb"
    main(["history", "import", "--output-dir", str(run_dir / "data"), "--db-path", str(db_path)])
    code = main(["history", "stats", "--db-path", str(db_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "HISTORICAL STORAGE STATS" in captured.out
    assert "Runs:           1" in captured.out
    assert "Source Jobs:    1" in captured.out


def test_cli_history_verify(run_dir: Path, capsys):
    db_path = run_dir / "db" / "history.duckdb"
    main(["history", "import", "--output-dir", str(run_dir / "data"), "--db-path", str(db_path)])
    code = main(["history", "verify", "--db-path", str(db_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "HISTORICAL STORAGE VERIFICATION" in captured.out
    assert "Missing Files:        0" in captured.out
    assert "Corrupt Files:        0" in captured.out
    assert "Orphan Files:         0" in captured.out
