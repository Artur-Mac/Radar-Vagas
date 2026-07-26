"""Connector registry — maps SourceType to connector factory functions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from radar_vagas.domain.models import SourceType

if TYPE_CHECKING:
    from radar_vagas.domain.connector import JobConnector
    from radar_vagas.domain.models import SourceConfig

logger = logging.getLogger("radar_vagas.sources.registry")

# Type alias for a connector factory: takes a SourceConfig, returns a connector.
ConnectorFactory = Callable[["SourceConfig"], "JobConnector"]


class ConnectorRegistry:
    """Registry that maps ``SourceType`` values to connector factories.

    Usage::

        registry = ConnectorRegistry()
        registry.register(SourceType.aggregator_api, RemotiveConnector)
        connector = registry.create(source_config)
    """

    def __init__(self) -> None:
        self._factories: dict[SourceType, ConnectorFactory] = {}

    def register(self, source_type: SourceType, factory: ConnectorFactory) -> None:
        """Register a factory for the given source type."""
        self._factories[source_type] = factory
        logger.debug("Registered connector factory for %s", source_type.value)

    def create(self, source_config: SourceConfig) -> JobConnector:
        """Instantiate a connector for *source_config*.

        Raises
        ------
        KeyError
            If no factory is registered for the config's ``source_type``.
        """
        factory = self._factories.get(source_config.source_type)
        if factory is None:
            msg = (
                f"No connector registered for source type "
                f"'{source_config.source_type.value}'. "
                f"Available: {[st.value for st in self._factories]}"
            )
            raise KeyError(msg)
        return factory(source_config)

    def available_types(self) -> list[SourceType]:
        """Return source types that have a registered factory."""
        return list(self._factories.keys())


def build_default_registry() -> ConnectorRegistry:
    """Build a registry pre-loaded with all built-in connector types."""
    # Lazy imports to avoid circular dependencies.

    from radar_vagas.connectors.greenhouse import GreenhouseConnector
    from radar_vagas.connectors.lever import LeverConnector
    from radar_vagas.connectors.remotive import RemotiveConnector

    registry = ConnectorRegistry()
    registry.register(SourceType.aggregator_api, RemotiveConnector)
    registry.register(SourceType.ats_greenhouse, GreenhouseConnector)
    registry.register(SourceType.ats_lever, LeverConnector)
    # Arbeitnow reuses the aggregator_api type — register under its own key
    # if we want separate handling, or let the catalog pick the right factory.
    # For now, we keep the registry keyed by SourceType, so aggregator_api
    # will default to RemotiveConnector. Individual connectors handle the
    # source-specific logic via SourceConfig.
    # We register Arbeitnow under a special-case handling in registry lookup
    # or allow overriding. For simplicity, we register all four:
    registry.register(SourceType.aggregator_api, _aggregator_factory)
    return registry


def _aggregator_factory(config: SourceConfig) -> JobConnector:
    """Route aggregator configs using the explicit catalog connector identifier."""
    from radar_vagas.connectors.arbeitnow import ArbeitnowConnector
    from radar_vagas.connectors.remotive import RemotiveConnector

    if config.connector == "arbeitnow":
        return ArbeitnowConnector(config)
    if config.connector == "remotive":
        return RemotiveConnector(config)
    msg = f"Unsupported aggregator connector for source '{config.name}': {config.connector!r}"
    raise ValueError(msg)
