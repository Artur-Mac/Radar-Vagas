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


@pytest.mark.parametrize("count", [300, 1000, 3000])
def test_import_run_scale_benchmark(tmp_path: Path, count: int):
    storage = HistoricalStorage(tmp_path / f"data_{count}")

    records = [
        RawJobRecord(
            source_name="perf_src",
            source_job_id=f"job_{i}",
            raw_payload=f'{{"key": "value_{i}", "url": "http://example.com/{i}"}}',
            source_url=f"http://example.com/{i}",
        )
        for i in range(count)
    ]

    manifest = RunManifest(
        summary=IngestionSummary(
            run_id=f"perf_run_{count}",
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
                    records_fetched=count,
                    records_valid=count,
                    coverage_complete=True,
                )
            },
        )
    )

    # 1. Measure CAS blob filesystem time alone
    cas_start = time.monotonic()
    for r in records:
        storage.write_blob(r.content_hash, r.raw_payload)
    cas_duration = time.monotonic() - cas_start

    # 2. Measure overall import (DB transaction + batching)
    db_start = time.monotonic()
    storage.import_run(manifest, records)
    total_duration = time.monotonic() - db_start

    print(
        f"\n[BENCHMARK {count} records] CAS Write: {cas_duration:.3f}s | Import Total: {total_duration:.3f}s"
    )

    # Assert regression budget: 3000 records must complete within 45s
    assert total_duration < 45.0, f"Import of {count} records took too long: {total_duration:.2f}s"

    db_jobs = storage.conn.execute("SELECT COUNT(*) FROM source_jobs").fetchone()[0]
    assert db_jobs == count

    storage.close()
