import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class WorkArrangement(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class RoleFamily(StrEnum):
    DATA_ENGINEER = "data_engineer"
    DATA_PLATFORM_ENGINEER = "data_platform_engineer"
    DATA_SCIENTIST = "data_scientist"
    MACHINE_LEARNING_ENGINEER = "machine_learning_engineer"
    ANALYTICS_ENGINEER = "analytics_engineer"
    MLOPS_ENGINEER = "mlops_engineer"
    AI_ENGINEER = "ai_engineer"
    BUSINESS_INTELLIGENCE_ENGINEER = "business_intelligence_engineer"
    TECHNICAL_DATA_ANALYST = "technical_data_analyst"
    DATA_ANALYST = "data_analyst"
    OTHER = "other"


class SeniorityLevel(StrEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    LEAD = "lead"
    PRINCIPAL = "principal"
    MANAGER = "manager"
    HEAD = "head"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class ConfidenceCategory(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FieldProvenance(BaseModel):
    """Provenance tracking for a transformed canonical field."""

    provenance_id: str = Field(default_factory=lambda: f"prov_{uuid.uuid4().hex[:12]}")
    normalized_job_id: str
    observation_id: str
    field_name: str
    original_value: str | None = None
    normalized_value: str | None = None
    extraction_rule: str
    rule_version: str = "1.0.0"
    confidence: ConfidenceCategory = ConfidenceCategory.HIGH
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def empty_string_to_none(self) -> Self:
        if self.original_value == "":
            self.original_value = None
        if self.normalized_value == "":
            self.normalized_value = None
        return self


class CanonicalJobPost(BaseModel):
    """Canonical Job Schema (Época 5).

    Missing values are represented explicitly as None/null (never empty strings or "unknown").
    """

    normalized_job_id: str
    source_name: str
    source_job_id: str
    observation_id: str
    raw_content_hash: str
    cleaned_id: str | None = None

    company_name: str | None = None
    job_title: str | None = None
    location_raw: str | None = None
    city: str | None = None
    state_or_region: str | None = None
    country_code: str | None = None  # ISO 3166-1 alpha-2 e.g. 'US', 'BR', 'DE'
    work_arrangement: WorkArrangement | None = None
    employment_type: EmploymentType | None = None
    published_at: datetime | None = None
    description: str | None = None
    application_url: str | None = None
    role_family: RoleFamily | None = None
    seniority: SeniorityLevel | None = None
    language: str | None = None
    normalization_rule_version: str = "1.0.0"
    normalized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    provenance: list[FieldProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def clean_empty_strings(self) -> Self:
        """Enforce strict representation of missing values as None instead of empty strings or 'unknown'."""
        for field_name in (
            "company_name",
            "job_title",
            "location_raw",
            "city",
            "state_or_region",
            "country_code",
            "description",
            "application_url",
            "language",
        ):
            val = getattr(self, field_name)
            if isinstance(val, str):
                stripped = val.strip()
                if not stripped or stripped.lower() in ("unknown", "n/a", "null", "none"):
                    setattr(self, field_name, None)
                elif stripped != val:
                    setattr(self, field_name, stripped)
        return self
