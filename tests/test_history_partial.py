from datetime import UTC, datetime
from pathlib import Path

from radar_vagas.domain.models import (
    IngestionSummary,
    RawJobRecord,
    RunManifest,
    RunState,
    SourceRunSummary,
)
from radar_vagas.infrastructure.history import HistoricalStorage


def test_missing_runs_ignores_partial_coverage(tmp_path: Path):
    history = HistoricalStorage(tmp_path)

    # Setup initial job
    rec1 = RawJobRecord(
        source_name="src_a",
        source_job_id="job_1",
        raw_payload="Payload 1",
        source_url="http://a/1",
        content_hash="5b4a9646a2f29587a8753dbd85691301d7010595e44c0a910d9cb2ae20ad132a",
    )

    manifest1 = RunManifest(
        summary=IngestionSummary(
            run_id="run_1",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            version="1.0",
            total_sources_requested=1,
            total_sources_executed=1,
            global_limit=None,
            per_source_limit=None,
            sources={
                "src_a": SourceRunSummary(
                    source_name="src_a",
                    state=RunState.success,
                    records_fetched=1,
                    records_valid=1,
                    coverage_complete=True,
                )
            },
        )
    )
    history.import_run(manifest1, [rec1])

    # Run 2: job_1 is NOT in the run, but coverage_complete=False (e.g. limit reached)
    manifest2 = RunManifest(
        summary=IngestionSummary(
            run_id="run_2",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            version="1.0",
            total_sources_requested=1,
            total_sources_executed=1,
            global_limit=5,
            per_source_limit=None,
            sources={
                "src_a": SourceRunSummary(
                    source_name="src_a",
                    state=RunState.success,
                    records_fetched=5,
                    records_valid=5,
                    coverage_complete=False,  # Important part
                )
            },
        )
    )

    history.import_run(manifest2, [])

    # Verify job is still active and missing_complete_runs is 0
    job = history.conn.execute(
        "SELECT status, missing_complete_runs FROM source_jobs WHERE source_job_id = 'job_1'"
    ).fetchone()
    assert job[0] == "active"
    assert job[1] == 0

    history.close()
