"""Unit tests for retention policy and pruning."""

from datetime import UTC, datetime
from pathlib import Path

from radar_vagas.domain.models import (
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

    storage.close()
