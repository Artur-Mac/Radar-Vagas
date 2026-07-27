import json
import time
from pathlib import Path

from radar_vagas.cli import main
from radar_vagas.core.normalization.service import NormalizationService
from radar_vagas.infrastructure.history import HistoricalStorage


def test_epoch5_e2e_end_to_end_validation_scenario(tmp_path: Path):
    data_dir = tmp_path / "data"
    runs_dir = data_dir / "runs" / "run_e2e_epoch5"
    raw_dir = runs_dir / "raw"
    raw_dir.mkdir(parents=True)

    manifest = {
        "summary": {
            "run_id": "run_e2e_epoch5",
            "started_at": "2026-07-26T20:00:00Z",
            "finished_at": "2026-07-26T20:00:05Z",
            "version": "0.1.0",
            "total_sources_requested": 2,
            "total_sources_executed": 2,
            "global_limit": None,
            "per_source_limit": None,
            "sources": {
                "remotive": {
                    "source_name": "remotive",
                    "state": "success",
                    "records_fetched": 1,
                    "records_valid": 1,
                    "coverage_complete": True,
                },
                "greenhouse_gitlab": {
                    "source_name": "greenhouse_gitlab",
                    "state": "success",
                    "records_fetched": 1,
                    "records_valid": 1,
                    "coverage_complete": True,
                },
            },
        }
    }
    (runs_dir / "manifest.json").write_text(json.dumps(manifest))

    (raw_dir / "remotive-1.json").write_text(
        json.dumps(
            {
                "source_name": "remotive",
                "source_job_id": "rem_101",
                "source_url": "https://remotive.com/jobs/rem_101",
                "raw_payload": json.dumps(
                    {
                        "id": "rem_101",
                        "title": "Senior Data Engineer",
                        "company_name": "DataCorp Inc.",
                        "url": "https://remotive.com/jobs/rem_101",
                        "candidate_required_location": "Worldwide",
                        "job_type": "full_time",
                        "description": "<h1>Data Engineering</h1><p>ETL with Python</p>",
                    }
                ),
            }
        )
    )

    (raw_dir / "greenhouse-1.json").write_text(
        json.dumps(
            {
                "source_name": "greenhouse_gitlab",
                "source_job_id": "gitlab_gh_202",
                "source_url": "https://boards.greenhouse.io/gitlab/jobs/gh_202",
                "raw_payload": json.dumps(
                    {
                        "id": "gh_202",
                        "title": "Lead Machine Learning Engineer",
                        "absolute_url": "https://boards.greenhouse.io/gitlab/jobs/gh_202",
                        "content": "<p>Develop ML models in Berlin</p>",
                        "location": {"name": "Berlin, Germany"},
                        "_board_identifier": "gitlab",
                    }
                ),
            }
        )
    )

    db_path = data_dir / "db" / "history.duckdb"
    backup_dir = tmp_path / "backups" / "snap_epoch5"
    restored_dir = tmp_path / "restored_data"

    # Step 1: Historical observation import
    t0 = time.monotonic()
    assert (
        main(["history", "import", "--output-dir", str(data_dir), "--db-path", str(db_path)]) == 0
    )
    t_import = time.monotonic() - t0

    # Step 2: Cleaning
    t0 = time.monotonic()
    assert main(["history", "clean", "--db-path", str(db_path)]) == 0
    t_clean = time.monotonic() - t0

    # Step 3: Normalization pass 1 (rule_version 1.0.0)
    t0 = time.monotonic()
    assert main(["normalize", "--db-path", str(db_path), "--rule-version", "1.0.0"]) == 0
    t_norm1 = time.monotonic() - t0

    # Step 4: Prove idempotency on second run with same rule_version 1.0.0
    with HistoricalStorage(data_dir, db_path=db_path) as history:
        service = NormalizationService(history)
        report_redo = service.normalize_batch(rule_version="1.0.0")
        assert report_redo.records_normalized == 0
        assert report_redo.records_skipped == 2

    # Step 5: Re-run with new rule version 1.1.0 and prove history is preserved
    t0 = time.monotonic()
    assert main(["normalize", "--db-path", str(db_path), "--rule-version", "1.1.0"]) == 0
    t_norm2 = time.monotonic() - t0

    with HistoricalStorage(data_dir, db_path=db_path) as history:
        all_norm_records = history.conn.execute(
            "SELECT count(*) FROM normalized_job_records"
        ).fetchone()[0]
        assert all_norm_records == 4  # 2 records for 1.0.0 + 2 records for 1.1.0

        latest = history.get_latest_normalized_records()
        assert len(latest) == 2
        assert latest[0].normalization_rule_version == "1.1.0"

    # Step 6: Backup & Restore
    assert (
        main(["history", "backup", "--dest-dir", str(backup_dir), "--db-path", str(db_path)]) == 0
    )
    assert (
        main(
            [
                "history",
                "restore",
                "--backup-dir",
                str(backup_dir),
                "--target-dir",
                str(restored_dir),
            ]
        )
        == 0
    )

    # Step 7: Normalized query on restored storage
    restored_db = restored_dir / "db" / "history.duckdb"
    with HistoricalStorage(restored_dir, db_path=restored_db) as restored_history:
        report = restored_history.verify_integrity()
        assert report.is_valid

        restored_latest = restored_history.get_latest_normalized_records()
        assert len(restored_latest) == 2
        assert restored_latest[0].company_name in ("DataCorp", "gitlab")

    print(
        f"\nEpoch 5 E2E Validation Complete! Import: {t_import:.3f}s | Clean: {t_clean:.3f}s | "
        f"Norm 1.0: {t_norm1:.3f}s | Norm 1.1: {t_norm2:.3f}s"
    )
