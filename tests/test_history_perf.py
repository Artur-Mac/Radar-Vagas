import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from radar_vagas.domain.models import (
    IngestionSummary,
    RawJobRecord,
    RunManifest,
    RunState,
    SourceRunSummary,
)
from radar_vagas.infrastructure.history import HistoricalStorage


@pytest.fixture
def temp_history(tmp_path: Path):
    storage = HistoricalStorage(tmp_path)
    yield storage
    storage.close()


def test_import_run_performance_benchmark(temp_history: HistoricalStorage):
    # Create 1000 records
    records = []
    for i in range(1000):
        records.append(
            RawJobRecord(
                source_name="perf_src",
                source_job_id=f"job_{i}",
                raw_payload=f'{{"data": "value_{i}"}}',
                source_url=f"http://example.com/{i}",
            )
        )

    manifest = RunManifest(
        summary=IngestionSummary(
            run_id="perf_run_1",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_seconds=1.0,
            total_sources_requested=1,
            total_sources_executed=1,
            version="1.0.0",
            global_limit=None,
            per_source_limit=None,
            sources={
                "perf_src": SourceRunSummary(
                    source_name="perf_src",
                    state=RunState.success,
                    records_fetched=1000,
                    records_valid=1000,
                    coverage_complete=True,
                )
            },
        )
    )

    start_time = time.monotonic()
    temp_history.import_run(manifest, records)
    duration = time.monotonic() - start_time

    # Check that 1000 insertions complete without timing out excessively.
    # Note: write_blob writes 1000 files to disk, which may be slow on some filesystems.
    assert duration < 30.0, f"Performance test failed, took {duration}s"

    jobs = temp_history.conn.execute("SELECT COUNT(*) FROM source_jobs").fetchone()[0]
    assert jobs == 1000
