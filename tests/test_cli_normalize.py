import hashlib
import json
from pathlib import Path

from radar_vagas.cli import main
from radar_vagas.infrastructure.history import HistoricalStorage


def test_cli_normalize(tmp_path: Path, capsys):
    data_dir = tmp_path / "data"
    db_path = str(data_dir / "db" / "history.duckdb")

    with HistoricalStorage(data_dir, db_path=Path(db_path)) as history:
        raw_payload = json.dumps(
            {
                "id": 5005,
                "title": "Senior Data Engineer",
                "company_name": "Tech Corp",
                "url": "https://remotive.com/jobs/5005",
                "candidate_required_location": "Worldwide",
                "job_type": "full_time",
                "publication_date": "2026-07-26T10:00:00Z",
                "description": "ETL in Python",
            }
        )
        content_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        history.write_blob(content_hash, raw_payload)

        history.conn.execute("INSERT INTO ingestion_runs (run_id) VALUES ('run_5005')")
        history.conn.execute(
            """
            INSERT INTO source_job_observations (
                observation_id, source_name, source_job_id, run_id, content_hash, observed_at, source_type
            ) VALUES ('obs_5005', 'remotive', '5005', 'run_5005', ?, '2026-07-26T10:00:00Z', 'aggregator_api')
            """,
            [content_hash],
        )

    # Dry-run CLI test
    code_dry = main(["normalize", "--db-path", db_path, "--dry-run"])
    assert code_dry == 0
    captured_dry = capsys.readouterr()
    assert "JOB NORMALIZATION [PREVIEW (DRY-RUN)]" in captured_dry.out
    assert "Records Normalized:      1" in captured_dry.out

    # Execution CLI test
    code_exec = main(["normalize", "--db-path", db_path])
    assert code_exec == 0
    captured_exec = capsys.readouterr()
    assert "JOB NORMALIZATION [EXECUTION]" in captured_exec.out
    assert "Records Normalized:      1" in captured_exec.out

    # Second execution CLI test (idempotent skip)
    code_skip = main(["normalize", "--db-path", db_path])
    assert code_skip == 0
    captured_skip = capsys.readouterr()
    assert "Records Skipped:         1" in captured_skip.out
