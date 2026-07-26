"""Unit tests for core ingestion pipeline (ConnectorRunner)."""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from radar_vagas.core.ingestion import ConnectorRunner
from radar_vagas.domain.connector import JobConnector
from radar_vagas.domain.models import (
    CanonicalJob,
    CollectionError,
    ConnectorResult,
    Pagination,
    RawJobRecord,
    RunState,
    SourceConfig,
    SourceType,
)
from radar_vagas.infrastructure.storage import LocalStorage
from radar_vagas.sources.registry import ConnectorRegistry


class DummyConnector:
    """A configurable dummy connector for ingestion tests."""

    def __init__(self, config: SourceConfig, fetch_side_effect=None):
        self._config = config
        self.fetch_side_effect = fetch_side_effect

    @property
    def source_config(self) -> SourceConfig:
        return self._config

    def fetch(
        self, client: httpx.Client, *, limit: int = 100, cursor: Pagination | None = None
    ) -> ConnectorResult:
        if self.fetch_side_effect:
            return self.fetch_side_effect(client, limit=limit, cursor=cursor)
        return ConnectorResult(source_name=self._config.name, state=RunState.success, records=[])

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        raise NotImplementedError("Not needed for ingestion runner tests")


@pytest.fixture
def offline_client() -> httpx.Client:
    """Fixture providing an offline HTTP client backed by MockTransport."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_empty_catalog(tmp_path: Path, offline_client: httpx.Client) -> None:
    """Test ingestion run with 0 sources in catalog."""
    registry = ConnectorRegistry()
    storage = LocalStorage(tmp_path)
    runner = ConnectorRunner(registry=registry, storage=storage, client=offline_client)

    manifest = runner.run([])

    assert manifest.summary.total_sources_requested == 0
    assert manifest.summary.total_sources_executed == 0
    assert manifest.summary.total_fetched == 0
    assert manifest.summary.total_valid == 0
    assert len(manifest.summary.sources) == 0


def test_successful_source_and_exact_deduplication(
    tmp_path: Path, offline_client: httpx.Client
) -> None:
    """Test successful source record generation and exact deduplication (by ID and content hash)."""
    config = SourceConfig(
        name="source_dedup",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/api",
    )

    rec1 = RawJobRecord(
        source_name="source_dedup",
        source_job_id="job_1",
        raw_payload="Data Analyst job posting",
        source_url="https://example.com/jobs/1",
    )
    # Same source_job_id as rec1 -> deduplicated by ID
    rec2_duplicate_id = RawJobRecord(
        source_name="source_dedup",
        source_job_id="job_1",
        raw_payload="Data Analyst duplicate job posting",
        source_url="https://example.com/jobs/1",
    )
    # Different source_job_id, same content_hash as rec1 -> deduplicated by content hash
    rec3_duplicate_hash = RawJobRecord(
        source_name="source_dedup",
        source_job_id="job_2",
        raw_payload="Data Analyst job posting",
        source_url="https://example.com/jobs/2",
    )
    # Unique record
    rec4_unique = RawJobRecord(
        source_name="source_dedup",
        source_job_id="job_3",
        raw_payload="Software Engineer job posting",
        source_url="https://example.com/jobs/3",
    )

    def fetch_handler(client, limit=100, cursor=None):
        return ConnectorResult(
            source_name="source_dedup",
            state=RunState.success,
            records=[rec1, rec2_duplicate_id, rec3_duplicate_hash, rec4_unique],
            records_fetched=4,
        )

    connector = DummyConnector(config, fetch_side_effect=fetch_handler)
    registry = ConnectorRegistry()
    registry.register(SourceType.aggregator_api, lambda cfg: connector)

    storage = LocalStorage(tmp_path)
    runner = ConnectorRunner(registry=registry, storage=storage, client=offline_client)

    manifest = runner.run([config])

    assert manifest.summary.total_sources_requested == 1
    assert manifest.summary.total_sources_executed == 1
    assert manifest.summary.total_fetched == 4
    assert manifest.summary.total_valid == 2
    assert manifest.summary.total_duplicated == 2

    source_summary = manifest.summary.sources["source_dedup"]
    assert source_summary.records_fetched == 4
    assert source_summary.records_valid == 2
    assert source_summary.records_duplicated == 2
    assert source_summary.state == RunState.success

    assert len(manifest.duplicates) == 2
    reasons = [d.reason for d in manifest.duplicates]
    assert "same_run_source_job_id" in reasons
    assert "same_run_content_hash" in reasons


def test_source_isolation(tmp_path: Path, offline_client: httpx.Client) -> None:
    """Test source isolation: one failing source does not stop execution of subsequent sources."""
    config_fail = SourceConfig(
        name="source_fail",
        source_type=SourceType.ats_greenhouse,
        base_url="https://example.com/fail",
    )
    config_ok = SourceConfig(
        name="source_ok",
        source_type=SourceType.ats_lever,
        base_url="https://example.com/ok",
    )

    def fetch_fail(client, limit=100, cursor=None):
        raise RuntimeError("Network timeout connecting to ATS")

    def fetch_ok(client, limit=100, cursor=None):
        rec = RawJobRecord(
            source_name="source_ok",
            source_job_id="ok_1",
            raw_payload="Data Engineer job",
            source_url="https://example.com/ok/1",
        )
        return ConnectorResult(
            source_name="source_ok",
            state=RunState.success,
            records=[rec],
            records_fetched=1,
        )

    registry = ConnectorRegistry()
    registry.register(
        SourceType.ats_greenhouse, lambda cfg: DummyConnector(cfg, fetch_side_effect=fetch_fail)
    )
    registry.register(
        SourceType.ats_lever, lambda cfg: DummyConnector(cfg, fetch_side_effect=fetch_ok)
    )

    storage = LocalStorage(tmp_path)
    runner = ConnectorRunner(registry=registry, storage=storage, client=offline_client)

    manifest = runner.run([config_fail, config_ok])

    assert manifest.summary.total_sources_requested == 2
    assert manifest.summary.total_sources_executed == 2
    assert manifest.summary.total_fetched == 1
    assert manifest.summary.total_valid == 1

    assert manifest.summary.sources["source_fail"].state == RunState.temporary_failure
    assert manifest.summary.sources["source_ok"].state == RunState.success
    assert manifest.summary.sources["source_ok"].records_valid == 1


def test_validation_missing_job_id_and_missing_payload(
    tmp_path: Path, offline_client: httpx.Client
) -> None:
    """Test minimal validation rejecting records with missing job ID or missing URL & payload."""
    config = SourceConfig(
        name="source_validation",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/api",
    )
    records = [
        RawJobRecord(
            source_name="source_validation",
            source_job_id="",
            raw_payload="Data Science role",
            source_url="https://example.com/jobs/1",
        ),
        RawJobRecord(
            source_name="source_validation",
            source_job_id="job_2",
            raw_payload="No URL",
            source_url=None,
        ),
        RawJobRecord(
            source_name="source_validation",
            source_job_id="job_3",
            raw_payload="",
            source_url="https://example.com/jobs/3",
        ),
    ]
    connector = DummyConnector(
        config,
        fetch_side_effect=lambda client, limit=100, cursor=None: ConnectorResult(
            source_name=config.name,
            records=records,
            records_fetched=len(records),
        ),
    )
    registry = ConnectorRegistry()
    registry.register(SourceType.aggregator_api, lambda cfg: connector)
    runner = ConnectorRunner(
        registry=registry,
        storage=LocalStorage(tmp_path),
        client=offline_client,
    )

    manifest = runner.run([config])

    assert manifest.summary.total_rejected == 3
    assert {record.reason for record in manifest.rejected} == {
        "missing_source_job_id",
        "missing_source_url",
        "missing_raw_payload",
    }


def test_fail_fast_invalid_configuration_persists_manifest(
    tmp_path: Path, offline_client: httpx.Client
) -> None:
    invalid = SourceConfig(
        name="invalid_source",
        source_type=SourceType.ats_greenhouse,
        base_url="https://example.com/invalid",
    )
    remaining = SourceConfig(
        name="remaining_source",
        source_type=SourceType.ats_lever,
        base_url="https://example.com/remaining",
    )
    runner = ConnectorRunner(
        registry=ConnectorRegistry(),
        storage=LocalStorage(tmp_path),
        client=offline_client,
    )

    manifest = runner.run([invalid, remaining], fail_fast=True)

    assert manifest.summary.total_sources_executed == 1
    assert manifest.summary.sources[invalid.name].state == RunState.invalid_configuration
    assert manifest.summary.sources[remaining.name].state == RunState.skipped_fail_fast
    assert (tmp_path / "runs" / manifest.summary.run_id / "manifest.json").exists()


def test_dry_run_does_not_create_files(tmp_path: Path, offline_client: httpx.Client) -> None:
    """A dry run computes a manifest without creating the run directory."""
    config = SourceConfig(
        name="source_dry_run",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/api",
    )
    record = RawJobRecord(
        source_name=config.name,
        source_type=config.source_type,
        source_job_id="job_1",
        raw_payload='{"title": "Data Engineer"}',
        source_url="https://example.com/jobs/1",
    )

    connector = DummyConnector(
        config,
        fetch_side_effect=lambda client, limit=100, cursor=None: ConnectorResult(
            source_name=config.name,
            records=[record],
            records_fetched=1,
        ),
    )
    registry = ConnectorRegistry()
    registry.register(SourceType.aggregator_api, lambda cfg: connector)
    runner = ConnectorRunner(
        registry=registry,
        storage=LocalStorage(tmp_path),
        client=offline_client,
    )

    manifest = runner.run([config], persist=False)

    assert manifest.summary.total_valid == 1
    assert not (tmp_path / "runs").exists()


def test_connector_error_is_not_reported_as_empty(
    tmp_path: Path, offline_client: httpx.Client
) -> None:
    """An error with no records is a failure, not a healthy empty source."""
    config = SourceConfig(
        name="source_error",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/api",
    )
    error = CollectionError(
        source_name=config.name,
        phase="fetch",
        message="service unavailable",
    )
    connector = DummyConnector(
        config,
        fetch_side_effect=lambda client, limit=100, cursor=None: ConnectorResult(
            source_name=config.name,
            records=[],
            errors=[error],
            records_failed=1,
        ),
    )
    registry = ConnectorRegistry()
    registry.register(SourceType.aggregator_api, lambda cfg: connector)
    runner = ConnectorRunner(
        registry=registry,
        storage=LocalStorage(tmp_path),
        client=offline_client,
    )

    manifest = runner.run([config])

    assert manifest.summary.sources[config.name].state == RunState.temporary_failure


def test_pagination_limits_and_loop_protection(
    tmp_path: Path, offline_client: httpx.Client
) -> None:
    """Test global limit, per-source limit, and pagination loop protection."""
    config1 = SourceConfig(
        name="source_paginated_1",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/api1",
    )
    config2 = SourceConfig(
        name="source_paginated_2",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/api2",
    )

    # 1. Test per_source_limit
    def fetch_paginated_1(client, limit=100, cursor=None):
        records = [
            RawJobRecord(
                source_name="source_paginated_1",
                source_job_id=f"p1_{i}",
                raw_payload="data engineer",
                source_url=f"https://example.com/p1_{i}",
            )
            for i in range(limit)
        ]
        next_page = Pagination(has_more=True, next_page_url="https://example.com/api1?page=2")
        return ConnectorResult(
            source_name="source_paginated_1",
            records=records,
            records_fetched=len(records),
            next_page=next_page,
        )

    registry1 = ConnectorRegistry()
    registry1.register(
        SourceType.aggregator_api,
        lambda cfg: DummyConnector(cfg, fetch_side_effect=fetch_paginated_1),
    )

    storage = LocalStorage(tmp_path)
    runner1 = ConnectorRunner(registry=registry1, storage=storage, client=offline_client)
    manifest1 = runner1.run([config1], per_source_limit=2)

    assert manifest1.summary.total_fetched == 2

    # 2. Test global_limit across 2 sources
    def fetch_paginated_2(client, limit=100, cursor=None):
        records = [
            RawJobRecord(
                source_name="source_paginated_2",
                source_job_id=f"p2_{i}",
                raw_payload="data scientist",
                source_url=f"https://example.com/p2_{i}",
            )
            for i in range(min(limit, 5))
        ]
        return ConnectorResult(
            source_name="source_paginated_2",
            records=records,
            records_fetched=len(records),
        )

    registry2 = ConnectorRegistry()
    registry2.register(
        SourceType.aggregator_api,
        lambda cfg: DummyConnector(
            cfg,
            fetch_side_effect=lambda c, limit=100, cursor=None: (
                fetch_paginated_1(c, limit, cursor)
                if cfg.name == "source_paginated_1"
                else fetch_paginated_2(c, limit, cursor)
            ),
        ),
    )

    runner2 = ConnectorRunner(registry=registry2, storage=storage, client=offline_client)
    manifest2 = runner2.run([config1, config2], global_limit=3)

    assert manifest2.summary.total_fetched == 3

    # 3. Test loop protection (same next_page_url repeatedly)
    page_count = 0

    def fetch_looping(client, limit=100, cursor=None):
        nonlocal page_count
        page_count += 1
        records = [
            RawJobRecord(
                source_name="source_loop",
                source_job_id=f"loop_{page_count}",
                raw_payload="data analyst",
                source_url="https://example.com/loop",
            )
        ]
        # Return same next_page_url repeatedly
        next_page = Pagination(has_more=True, next_page_url="https://example.com/stuck_page")
        return ConnectorResult(
            source_name="source_loop",
            records=records,
            records_fetched=1,
            next_page=next_page,
        )

    config_loop = SourceConfig(
        name="source_loop",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/loop",
    )
    registry3 = ConnectorRegistry()
    registry3.register(
        SourceType.aggregator_api,
        lambda cfg: DummyConnector(cfg, fetch_side_effect=fetch_looping),
    )

    runner3 = ConnectorRunner(registry=registry3, storage=storage, client=offline_client)
    manifest3 = runner3.run([config_loop])

    # Should break loop after detecting repeated next_page_url (2 iterations)
    assert page_count == 2
    assert manifest3.summary.total_fetched == 2


def test_data_ai_relevance_filter(tmp_path: Path, offline_client: httpx.Client) -> None:
    """Test Data/AI relevance regex filter counting relevant records."""
    config = SourceConfig(
        name="source_relevance",
        source_type=SourceType.aggregator_api,
        base_url="https://example.com/api",
    )

    recs = [
        RawJobRecord(
            source_name="source_relevance",
            source_job_id="r1",
            raw_payload="We are hiring a Senior Data Engineer",
            source_url="https://example.com/r1",
        ),
        RawJobRecord(
            source_name="source_relevance",
            source_job_id="r2",
            raw_payload="Machine Learning Specialist needed",
            source_url="https://example.com/r2",
        ),
        RawJobRecord(
            source_name="source_relevance",
            source_job_id="r3",
            raw_payload="AI & MLOps Infrastructure Architect",
            source_url="https://example.com/r3",
        ),
        RawJobRecord(
            source_name="source_relevance",
            source_job_id="r4",
            raw_payload="Senior React Frontend Developer",
            source_url="https://example.com/r4",
        ),
    ]

    def fetch_handler(client, limit=100, cursor=None):
        return ConnectorResult(
            source_name="source_relevance",
            records=recs,
            records_fetched=4,
        )

    registry = ConnectorRegistry()
    registry.register(
        SourceType.aggregator_api,
        lambda cfg: DummyConnector(cfg, fetch_side_effect=fetch_handler),
    )

    storage = LocalStorage(tmp_path)
    runner = ConnectorRunner(registry=registry, storage=storage, client=offline_client)

    manifest = runner.run([config])

    assert manifest.summary.total_fetched == 4
    assert manifest.summary.total_valid == 4
    assert manifest.summary.total_relevant == 3
    assert manifest.summary.sources["source_relevance"].records_relevant == 3


def test_mocked_connector_spec(tmp_path: Path, offline_client: httpx.Client) -> None:
    """Test ConnectorRunner using MagicMock with spec=JobConnector."""
    config = SourceConfig(
        name="source_mocked",
        source_type=SourceType.ats_greenhouse,
        base_url="https://example.com/mocked",
    )

    mock_connector = MagicMock(spec=JobConnector)
    mock_connector.source_config = config
    rec = RawJobRecord(
        source_name="source_mocked",
        source_job_id="m1",
        raw_payload="Lead Data Scientist",
        source_url="https://example.com/m1",
    )
    mock_connector.fetch.return_value = ConnectorResult(
        source_name="source_mocked",
        records=[rec],
        records_fetched=1,
    )

    registry = ConnectorRegistry()
    registry.register(SourceType.ats_greenhouse, lambda cfg: mock_connector)

    storage = LocalStorage(tmp_path)
    runner = ConnectorRunner(registry=registry, storage=storage, client=offline_client)

    manifest = runner.run([config])

    assert manifest.summary.total_fetched == 1
    assert manifest.summary.total_valid == 1
    assert manifest.summary.total_relevant == 1
    mock_connector.fetch.assert_called_once()
