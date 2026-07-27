import hashlib
import json
from pathlib import Path

from radar_vagas.core.normalization.service import NormalizationService
from radar_vagas.domain.models import CleanedSourceText
from radar_vagas.infrastructure.history import HistoricalStorage


def test_normalization_service_idempotency_and_versioning(tmp_path: Path):
    storage_dir = tmp_path / "data"
    with HistoricalStorage(storage_dir) as history:
        # Insert test run, blob, observation, and cleaned text
        raw_payload = json.dumps(
            {
                "id": 1001,
                "title": "Senior Data Engineer",
                "company_name": "Acme Corp",
                "url": "https://remotive.com/jobs/1001",
                "candidate_required_location": "Worldwide",
                "job_type": "full_time",
                "publication_date": "2026-07-26T10:00:00Z",
                "description": "ETL in Python",
            }
        )
        content_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        history.write_blob(content_hash, raw_payload)

        history.conn.execute(
            "INSERT INTO ingestion_runs (run_id, started_at) VALUES ('run_test', '2026-07-26T10:00:00Z')"
        )
        history.conn.execute(
            """
            INSERT INTO source_job_observations (
                observation_id, source_name, source_job_id, run_id, content_hash, observed_at, source_type
            ) VALUES ('obs_1001', 'remotive', '1001', 'run_test', ?, '2026-07-26T10:00:00Z', 'aggregator_api')
            """,
            [content_hash],
        )

        service = NormalizationService(history)

        # First normalization pass with rule version 1.0.0
        report1 = service.normalize_batch(rule_version="1.0.0")
        assert report1.observations_discovered == 1
        assert report1.records_normalized == 1
        assert report1.records_skipped == 0
        assert report1.records_quarantined == 0

        # Second normalization pass with same rule version -> should be skipped (idempotent)
        report2 = service.normalize_batch(rule_version="1.0.0")
        assert report2.observations_discovered == 1
        assert report2.records_normalized == 0
        assert report2.records_skipped == 1

        # Re-running with a new rule version 1.1.0 -> creates a new version
        report3 = service.normalize_batch(rule_version="1.1.0")
        assert report3.observations_discovered == 1
        assert report3.records_normalized == 1
        assert report3.records_skipped == 0

        # Query latest normalized records -> verify version 1.1.0 is returned
        latest = history.get_latest_normalized_records()
        assert len(latest) == 1
        assert latest[0].normalization_rule_version == "1.1.0"

        # Verify previous version 1.0.0 is still in database (version history preserved)
        all_count = history.conn.execute("SELECT COUNT(*) FROM normalized_job_records").fetchone()[
            0
        ]
        assert all_count == 2


def test_normalization_service_dry_run_does_not_mutate(tmp_path: Path):
    storage_dir = tmp_path / "data"
    with HistoricalStorage(storage_dir) as history:
        raw_payload = json.dumps(
            {
                "id": 2002,
                "title": "Data Analyst",
                "company_name": "DataCo",
                "url": "https://remotive.com/jobs/2002",
            }
        )
        content_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        history.write_blob(content_hash, raw_payload)

        history.conn.execute("INSERT INTO ingestion_runs (run_id) VALUES ('run_dry')")
        history.conn.execute(
            """
            INSERT INTO source_job_observations (
                observation_id, source_name, source_job_id, run_id, content_hash, observed_at, source_type
            ) VALUES ('obs_2002', 'remotive', '2002', 'run_dry', ?, '2026-07-26T10:00:00Z', 'aggregator_api')
            """,
            [content_hash],
        )

        service = NormalizationService(history)
        report = service.normalize_batch(dry_run=True)

        assert report.records_normalized == 1

        # Verify no database records were inserted in dry-run mode
        db_count = history.conn.execute("SELECT COUNT(*) FROM normalized_job_records").fetchone()[0]
        assert db_count == 0


def test_normalization_quarantine_on_invalid_payload(tmp_path: Path):
    storage_dir = tmp_path / "data"
    with HistoricalStorage(storage_dir) as history:
        # Store invalid non-JSON payload in blob
        payload_str = "{ invalid json ..."
        content_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        history.write_blob(content_hash, payload_str)

        history.conn.execute("INSERT INTO ingestion_runs (run_id) VALUES ('run_bad')")
        history.conn.execute(
            """
            INSERT INTO source_job_observations (
                observation_id, source_name, source_job_id, run_id, content_hash, observed_at, source_type
            ) VALUES ('obs_9999', 'remotive', '9999', 'run_bad', ?, '2026-07-26T10:00:00Z', 'aggregator_api')
            """,
            [content_hash],
        )

        service = NormalizationService(history)
        report = service.normalize_batch()

        assert report.records_rejected == 1
        assert report.records_quarantined == 1

        # Verify historical_quarantine table contains record with failure_phase="normalize"
        quarantine_rows = history.conn.execute(
            "SELECT failure_phase, error_type FROM historical_quarantine WHERE failure_phase = 'normalize'"
        ).fetchall()
        assert len(quarantine_rows) == 1
        assert quarantine_rows[0][0] == "normalize"


def test_changed_observations_get_distinct_ids_and_one_latest_cleaned_artifact(
    tmp_path: Path,
):
    with HistoricalStorage(tmp_path / "data") as history:
        payloads = [
            json.dumps(
                {
                    "id": 7007,
                    "title": "Data Engineer",
                    "company_name": "Acme",
                    "url": "https://remotive.com/jobs/7007",
                    "description": "Original description",
                }
            ),
            json.dumps(
                {
                    "id": 7007,
                    "title": "Senior Data Engineer",
                    "company_name": "Acme",
                    "url": "https://remotive.com/jobs/7007",
                    "description": "Changed description",
                }
            ),
        ]
        hashes = [hashlib.sha256(payload.encode()).hexdigest() for payload in payloads]
        for index, (payload, content_hash) in enumerate(
            zip(payloads, hashes, strict=True), start=1
        ):
            history.write_blob(content_hash, payload)
            history.conn.execute(
                "INSERT INTO ingestion_runs (run_id) VALUES (?)",
                [f"run_changed_{index}"],
            )
            history.conn.execute(
                """
                INSERT INTO source_job_observations (
                    observation_id, source_name, source_job_id, run_id,
                    content_hash, observed_at, source_type
                ) VALUES (?, 'remotive', '7007', ?, ?, ?, 'aggregator_api')
                """,
                [
                    f"obs_changed_{index}",
                    f"run_changed_{index}",
                    content_hash,
                    f"2026-07-2{index}T10:00:00Z",
                ],
            )

        history.save_cleaned_text(
            CleanedSourceText(
                cleaned_id="cleaned-old",
                observation_id="obs_changed_1",
                raw_content_hash=hashes[0],
                transformation_version="1.0.0",
                cleaned_text="Old cleaned text",
            )
        )
        history.save_cleaned_text(
            CleanedSourceText(
                cleaned_id="cleaned-new",
                observation_id="obs_changed_1",
                raw_content_hash=hashes[0],
                transformation_version="2.0.0",
                cleaned_text="New cleaned text",
            )
        )

        report = NormalizationService(history).normalize_batch()

        assert report.observations_discovered == 2
        assert report.records_normalized == 2
        rows = history.conn.execute(
            """
            SELECT normalized_job_id, observation_id, cleaned_id
            FROM normalized_job_records
            ORDER BY observation_id
            """
        ).fetchall()
        assert len({row[0] for row in rows}) == 2
        assert rows[0][2] == "cleaned-new"
