"""Unit tests for retention policy and pruning."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from radar_vagas.domain.canonical import CanonicalJobPost
from radar_vagas.domain.models import (
    CleanedSourceText,
    IngestionSummary,
    RawJobRecord,
    RetentionPolicy,
    RunManifest,
    RunState,
    SourceRunSummary,
)
from radar_vagas.infrastructure.history import HistoricalStorage


def test_retention_preview_does_not_mutate_data(tmp_path: Path):
    storage = HistoricalStorage(tmp_path / "data")

    # Create 6 runs
    for i in range(6):
        rec = RawJobRecord(
            source_name="src_ret",
            source_job_id=f"job_{i}",
            source_url=f"http://example.com/{i}",
            raw_payload=f'{{"data": "{i}"}}',
            collected_at=datetime.now(UTC),
        )
        manifest = RunManifest(
            summary=IngestionSummary(
                run_id=f"run_ret_{i}",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                version="0.1.0",
                total_sources_requested=1,
                total_sources_executed=1,
                global_limit=None,
                per_source_limit=None,
                sources={
                    "src_ret": SourceRunSummary(
                        source_name="src_ret",
                        state=RunState.success,
                        records_fetched=1,
                        records_valid=1,
                        coverage_complete=True,
                    )
                },
            )
        )
        storage.import_run(manifest, [rec])

    oldest_observation = storage.conn.execute(
        """
        SELECT observation_id, content_hash
        FROM source_job_observations
        WHERE run_id = 'run_ret_0'
        """
    ).fetchone()
    cleaned = CleanedSourceText(
        cleaned_id="cleaned-retention-test",
        observation_id=oldest_observation[0],
        raw_content_hash=oldest_observation[1],
        cleaned_text="cleaned",
    )
    storage.save_cleaned_text(cleaned)
    storage.save_normalized_records(
        [
            CanonicalJobPost(
                normalized_job_id="normalized-retention-test",
                source_name="src_ret",
                source_job_id="job_0",
                observation_id=oldest_observation[0],
                raw_content_hash=oldest_observation[1],
                cleaned_id=cleaned.cleaned_id,
            )
        ]
    )

    policy = RetentionPolicy(active=True, keep_minimum_runs=3)

    # Preview mode (force=False)
    report = storage.prune_retention(policy, force=False)
    assert report.preview_only is True
    assert report.pruned_runs == 3
    assert report.pruned_observations == 3

    # Assert no data was actually deleted
    count = storage.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
    assert count == 6

    # Destructive execution (force=True)
    report_exec = storage.prune_retention(policy, force=True)
    assert report_exec.preview_only is False
    assert report_exec.pruned_runs == 3

    # Assert 3 runs remain
    count_after = storage.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
    assert count_after == 3
    jobs_after = storage.conn.execute("SELECT COUNT(*) FROM source_jobs").fetchone()[0]
    assert jobs_after == 3
    links_after = storage.conn.execute("SELECT COUNT(*) FROM normalized_job_links").fetchone()[0]
    assert links_after == 0
    normalized_after = storage.conn.execute(
        "SELECT COUNT(*) FROM normalized_job_records"
    ).fetchone()[0]
    assert normalized_after == 0
    provenance_after = storage.conn.execute(
        "SELECT COUNT(*) FROM normalized_field_provenance"
    ).fetchone()[0]
    assert provenance_after == 0
    assert storage.verify_integrity().is_valid

    storage.close()


def test_retention_policy_rejects_unsafe_bounds():
    with pytest.raises(ValidationError, match="max_age_days"):
        RetentionPolicy(active=True, max_age_days=-1)

    with pytest.raises(ValidationError, match="keep_minimum_runs"):
        RetentionPolicy(active=True, keep_minimum_runs=0)
