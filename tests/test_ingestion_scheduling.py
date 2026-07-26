from pathlib import Path
from unittest.mock import MagicMock

import httpx

from radar_vagas.core.ingestion import ConnectorRunner
from radar_vagas.domain.models import (
    ConnectorResult,
    Pagination,
    RawJobRecord,
    RunState,
    SourceConfig,
    SourceType,
)
from radar_vagas.infrastructure.storage import LocalStorage
from radar_vagas.sources.registry import ConnectorRegistry
from tests.test_ingestion import DummyConnector


def test_fair_ingestion_scheduling(tmp_path: Path):
    storage = LocalStorage(tmp_path / "data")
    registry = ConnectorRegistry()

    # We create two sources that each return infinite items
    config_a = SourceConfig(
        name="src_a", source_type=SourceType.aggregator_api, base_url="http://a"
    )
    config_b = SourceConfig(
        name="src_b", source_type=SourceType.aggregator_api, base_url="http://b"
    )

    fetch_calls_a = []
    fetch_calls_b = []

    def fetch_a(client, limit, cursor):
        fetch_calls_a.append(limit)
        return ConnectorResult(
            source_name="src_a",
            state=RunState.success,
            records=[
                RawJobRecord(
                    source_name="src_a",
                    source_job_id=f"a{i}",
                    raw_payload="Data data",
                    source_url="a",
                )
                for i in range(limit)
            ],
            next_page=Pagination(has_more=True, next_page_url=f"http://a/{len(fetch_calls_a)}"),
        )

    def fetch_b(client, limit, cursor):
        fetch_calls_b.append(limit)
        return ConnectorResult(
            source_name="src_b",
            state=RunState.success,
            records=[
                RawJobRecord(
                    source_name="src_b",
                    source_job_id=f"b{i}",
                    raw_payload="Data data",
                    source_url="b",
                )
                for i in range(limit)
            ],
            next_page=Pagination(has_more=True, next_page_url=f"http://b/{len(fetch_calls_b)}"),
        )

    conn_a = DummyConnector(config_a, fetch_side_effect=fetch_a)
    conn_b = DummyConnector(config_b, fetch_side_effect=fetch_b)

    registry.register(SourceType.aggregator_api, lambda c: conn_a if c.name == "src_a" else conn_b)

    client = MagicMock(spec=httpx.Client)
    runner = ConnectorRunner(registry, storage, client)

    # Global limit 10, quantum 2. Should fetch 2 from A, 2 from B, 2 from A, 2 from B, 2 from A
    manifest = runner.run([config_a, config_b], global_limit=10, scheduling_quantum=2)

    assert manifest.summary.total_fetched == 10

    # A should be called 3 times (2, 2, 2) and B should be called 2 times (2, 2)
    # The sum of fetched records should be 10.
    assert sum(fetch_calls_a) + sum(fetch_calls_b) == 10
    assert len(fetch_calls_a) == 3
    assert len(fetch_calls_b) == 2

    assert manifest.summary.sources["src_a"].records_fetched == 6
    assert manifest.summary.sources["src_b"].records_fetched == 4
