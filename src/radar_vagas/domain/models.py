"""Core domain data models for Radar-Vagas."""

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """Supported job source types."""

    aggregator_api = "aggregator_api"
    ats_greenhouse = "ats_greenhouse"
    ats_lever = "ats_lever"
    ats_ashby = "ats_ashby"
    rss_feed = "rss_feed"
    career_page = "career_page"


# ---------------------------------------------------------------------------
# Core Job Models
# ---------------------------------------------------------------------------


class RawJobRecord(BaseModel):
    """Raw job payload preserved from source."""

    source_name: str
    source_type: SourceType | None = None
    source_job_id: str
    content_hash: str
    raw_payload: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_url: str | None = None


class CanonicalJob(BaseModel):
    """Normalized internal representation of a job posting."""

    job_id: str
    source_name: str
    source_job_id: str
    source_url: str | None = None
    application_url: str | None = None

    title_raw: str
    title_normalized: str
    company_raw: str
    company_normalized: str

    description_raw: str
    description_clean: str

    location_raw: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None

    work_arrangement: Literal["remote", "hybrid", "on_site", "unknown"] = "unknown"
    employment_type: Literal["full_time", "part_time", "contract", "internship", "unknown"] = (
        "unknown"
    )

    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Service Diagnostics
# ---------------------------------------------------------------------------


class ServiceDiagnostic(BaseModel):
    """Structured diagnostic status for local LLM service."""

    server_available: bool
    server_url: str
    configured_model: str
    model_installed: bool
    available_models: list[str] = Field(default_factory=list)
    message: str


# ---------------------------------------------------------------------------
# Source Catalog Models
# ---------------------------------------------------------------------------


class SourceConfig(BaseModel):
    """Configuration for a single job data source, loaded from TOML catalog."""

    name: str
    source_type: SourceType
    base_url: AnyHttpUrl
    active: bool = True
    connector: Literal["remotive", "arbeitnow", "greenhouse", "lever"] | None = None

    # ATS-specific identifiers
    board_identifier: str | None = None
    company_identifier: str | None = None

    # HTTP policy overrides (defaults applied by HttpPolicy)
    request_timeout: float = 15.0
    max_retries: int = 3
    rate_limit_delay: float = 1.0

    # Metadata
    description: str = ""
    career_url: str | None = None


class CollectionError(BaseModel):
    """Structured error captured during connector execution."""

    source_name: str
    phase: Literal["fetch", "normalize"]
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConnectorResult(BaseModel):
    """Execution result from a single connector run."""

    source_name: str
    records: list[RawJobRecord] = Field(default_factory=list)
    records_fetched: int = 0
    records_normalized: int = 0
    records_failed: int = 0
    errors: list[CollectionError] = Field(default_factory=list)
    duration_seconds: float = 0.0
