"""Core domain data models for Radar-Vagas."""

import hashlib
from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

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


class RunState(str, Enum):
    """Explicit states for a source collection run."""

    success = "success"
    empty = "empty"
    partial = "partial"
    temporary_failure = "temporary_failure"
    permanent_failure = "permanent_failure"
    disabled = "disabled"
    skipped_global_limit = "skipped_global_limit"
    skipped_fail_fast = "skipped_fail_fast"
    invalid_configuration = "invalid_configuration"


# ---------------------------------------------------------------------------
# Core Job Models
# ---------------------------------------------------------------------------


class RawJobRecord(BaseModel):
    """Raw job payload preserved from source."""

    source_name: str
    source_type: SourceType | None = None
    source_job_id: str
    content_hash: str = ""
    raw_payload: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_url: str | None = None

    @model_validator(mode="after")
    def validate_and_hash(self) -> "RawJobRecord":
        recomputed = hashlib.sha256(self.raw_payload.encode("utf-8")).hexdigest()
        if self.content_hash and self.content_hash != recomputed:
            raise ValueError(
                f"content_hash mismatch: expected {recomputed}, got {self.content_hash}"
            )
        self.content_hash = recomputed

        return self


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

    # Governance
    access_type: Literal["public", "authenticated", "paid", "unknown"] = "unknown"
    authentication_required: bool = False
    credential_env_var: str | None = None
    documented_rate_limit: str | None = None
    terms_url: str | None = None
    redistribution_policy: str | None = None
    retention_notes: str | None = None
    attribution_required: bool | None = None
    reviewed_at: datetime | None = None


class CollectionError(BaseModel):
    """Structured error captured during connector execution."""

    source_name: str
    phase: Literal["fetch", "normalize"]
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Pagination(BaseModel):
    """Pagination contract for connector fetch loops."""

    cursor: str | None = None
    page: int | None = None
    next_page_url: str | None = None
    has_more: bool = False


class ConnectorResult(BaseModel):
    """Execution result from a single connector run."""

    source_name: str
    state: RunState = RunState.success
    records: list[RawJobRecord] = Field(default_factory=list)
    records_fetched: int = 0
    records_normalized: int = 0
    records_failed: int = 0
    errors: list[CollectionError] = Field(default_factory=list)
    duration_seconds: float = 0.0
    next_page: Pagination | None = None


# ---------------------------------------------------------------------------
# Ingestion & Manifest Models
# ---------------------------------------------------------------------------


class RejectedRecord(BaseModel):
    """A record rejected during minimal validation."""

    source_name: str
    source_job_id: str | None = None
    reason: str


class QuarantinedRecord(BaseModel):
    """A record quarantined due to parsing/schema errors."""

    source_name: str
    source_job_id: str | None = None
    error_type: str
    message: str
    phase: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_payload: str | None = None


class ExactDuplicate(BaseModel):
    """A record detected as an exact duplicate during the run."""

    source_name: str
    source_job_id: str
    reason: str = "same_run_content_hash"


class SourceRunSummary(BaseModel):
    """Summary metrics for a single source execution."""

    source_name: str
    state: RunState
    coverage_complete: bool = False
    records_fetched: int = 0
    records_valid: int = 0
    records_rejected: int = 0
    records_quarantined: int = 0
    records_duplicated: int = 0
    records_relevant: int = 0
    duration_seconds: float = 0.0
    errors: list[CollectionError] = Field(default_factory=list)


class IngestionSummary(BaseModel):
    """Global summary of an ingestion run."""

    run_id: str
    started_at: datetime
    finished_at: datetime
    version: str
    total_sources_requested: int
    total_sources_executed: int
    global_limit: int | None
    per_source_limit: int | None

    total_fetched: int = 0
    total_valid: int = 0
    total_rejected: int = 0
    total_quarantined: int = 0
    total_duplicated: int = 0
    total_relevant: int = 0

    sources: dict[str, SourceRunSummary] = Field(default_factory=dict)
    duration_seconds: float = 0.0


class RunManifest(BaseModel):
    """Full manifest of a completed run, written to disk."""

    summary: IngestionSummary
    rejected: list[RejectedRecord] = Field(default_factory=list)
    quarantined: list[QuarantinedRecord] = Field(default_factory=list)
    duplicates: list[ExactDuplicate] = Field(default_factory=list)
