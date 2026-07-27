from radar_vagas.domain.canonical import (
    CanonicalJobPost,
    ConfidenceCategory,
    EmploymentType,
    FieldProvenance,
    RoleFamily,
    SeniorityLevel,
    WorkArrangement,
)


def test_canonical_job_post_missing_values_converted_to_none():
    job = CanonicalJobPost(
        normalized_job_id="norm_123",
        source_name="remotive",
        source_job_id="job_456",
        observation_id="obs_789",
        raw_content_hash="a" * 64,
        company_name="   ",  # whitespace -> None
        job_title="unknown",  # "unknown" -> None
        location_raw="N/A",  # "N/A" -> None
        country_code="US",
        work_arrangement=WorkArrangement.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        role_family=RoleFamily.DATA_ENGINEER,
        seniority=SeniorityLevel.SENIOR,
    )

    assert job.company_name is None
    assert job.job_title is None
    assert job.location_raw is None
    assert job.country_code == "US"
    assert job.work_arrangement == WorkArrangement.REMOTE
    assert job.employment_type == EmploymentType.FULL_TIME
    assert job.role_family == RoleFamily.DATA_ENGINEER
    assert job.seniority == SeniorityLevel.SENIOR


def test_field_provenance_model():
    prov = FieldProvenance(
        normalized_job_id="norm_123",
        observation_id="obs_789",
        field_name="role_family",
        original_value="Senior Data Pipeline Engineer",
        normalized_value="data_engineer",
        extraction_rule="rule_title_keyword",
        rule_version="1.0.0",
        confidence=ConfidenceCategory.HIGH,
    )

    assert prov.provenance_id.startswith("prov_")
    assert prov.original_value == "Senior Data Pipeline Engineer"
    assert prov.normalized_value == "data_engineer"
    assert prov.confidence == ConfidenceCategory.HIGH
