"""Connector protocol — structural interface for all job source connectors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import httpx

    from radar_vagas.domain.models import (
        CanonicalJob,
        ConnectorResult,
        Pagination,
        RawJobRecord,
        SourceConfig,
    )


@runtime_checkable
class JobConnector(Protocol):
    """Contract that every job source connector must satisfy.

    Connectors receive an ``httpx.Client`` to allow centralised HTTP policy
    (timeouts, retries, user-agent) and easy mocking in tests.
    """

    @property
    def source_config(self) -> SourceConfig:
        """Return the source configuration driving this connector."""
        ...

    def fetch(
        self, client: httpx.Client, *, limit: int = 100, cursor: Pagination | None = None
    ) -> ConnectorResult:
        """Fetch raw records from the source, returning a structured result."""
        ...

    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        """Transform a single raw record into the canonical job schema."""
        ...
