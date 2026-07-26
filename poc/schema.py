"""Canonical Data Schema for Radar-Vagas PoC."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class RawJobRecord(BaseModel):
    """Raw job payload preserved from source."""

    source_name: str
    source_job_id: str
    content_hash: str
    raw_payload: str  # JSON or raw text string
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


class ExtractedSkill(BaseModel):
    name: str
    requirement_type: Literal["required", "preferred"] = "required"
    evidence: str | None = None


class LLMEnrichmentResult(BaseModel):
    """Structured extraction output from local LLM."""

    role_family: Literal[
        "data_engineering",
        "analytics_engineering",
        "data_science",
        "machine_learning",
        "mlops",
        "ai_engineering",
        "data_platform",
        "business_intelligence",
        "other",
    ]
    seniority: Literal[
        "internship",
        "entry_level",
        "junior",
        "mid_level",
        "senior",
        "staff_lead",
        "executive",
        "unknown",
    ]
    technical_skills: list[ExtractedSkill] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    minimum_years_experience: int | None = None
    education_required: bool = False
    required_languages: list[str] = Field(default_factory=list)
    work_arrangement: Literal["remote", "hybrid", "on_site", "unknown"] = "unknown"
    summary: str = ""
    is_valid_json: bool = True
    extraction_latency_seconds: float = 0.0
