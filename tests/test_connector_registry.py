"""Unit tests for connector registry and factory routing in radar_vagas.sources.registry."""

import pytest

from radar_vagas.connectors.arbeitnow import ArbeitnowConnector
from radar_vagas.connectors.remotive import RemotiveConnector
from radar_vagas.domain.models import SourceConfig, SourceType
from radar_vagas.sources.registry import ConnectorRegistry, build_default_registry


def test_registry_register_and_create() -> None:
    """Verify registering a custom factory and creating a connector instance from config."""
    registry = ConnectorRegistry()
    dummy_connector = object()

    def fake_factory(config: SourceConfig) -> object:
        return dummy_connector

    registry.register(SourceType.ats_greenhouse, fake_factory)

    config = SourceConfig(
        name="Greenhouse Source",
        source_type=SourceType.ats_greenhouse,
        base_url="https://boards.greenhouse.io",
    )

    connector = registry.create(config)
    assert connector is dummy_connector


def test_registry_unknown_type_raises_key_error() -> None:
    """Verify creating a connector with an unregistered SourceType raises KeyError."""
    registry = ConnectorRegistry()
    config = SourceConfig(
        name="Unregistered RSS Source",
        source_type=SourceType.rss_feed,
        base_url="https://example.com/feed.xml",
    )

    with pytest.raises(KeyError, match="No connector registered for source type"):
        registry.create(config)


def test_registry_available_types() -> None:
    """Verify available_types returns all registered SourceType values."""
    registry = ConnectorRegistry()
    registry.register(SourceType.ats_lever, lambda cfg: None)
    registry.register(SourceType.ats_ashby, lambda cfg: None)

    available = registry.available_types()

    assert len(available) == 2
    assert SourceType.ats_lever in available
    assert SourceType.ats_ashby in available


def test_build_default_registry_has_all_types() -> None:
    """Verify build_default_registry includes default source types."""
    registry = build_default_registry()
    available = registry.available_types()

    assert SourceType.ats_greenhouse in available
    assert SourceType.ats_lever in available
    assert SourceType.aggregator_api in available


def test_aggregator_factory_routes_arbeitnow() -> None:
    """Verify aggregator factory routes configs containing 'arbeitnow' to ArbeitnowConnector."""
    registry = build_default_registry()
    config = SourceConfig(
        name="Arbeitnow Public API",
        source_type=SourceType.aggregator_api,
        connector="arbeitnow",
        base_url="https://www.arbeitnow.com/api/v1/jobs",
    )

    connector = registry.create(config)
    assert isinstance(connector, ArbeitnowConnector)


def test_aggregator_factory_routes_remotive() -> None:
    """Verify aggregator factory routes configs containing 'remotive' to RemotiveConnector."""
    registry = build_default_registry()
    config = SourceConfig(
        name="Remotive Remote API",
        source_type=SourceType.aggregator_api,
        connector="remotive",
        base_url="https://remotive.com/api/remote-jobs",
    )

    connector = registry.create(config)
    assert isinstance(connector, RemotiveConnector)
