import pytest

from radar_vagas.core.normalization.adapters.arbeitnow import ArbeitnowNormalizer
from radar_vagas.core.normalization.adapters.greenhouse import GreenhouseNormalizer
from radar_vagas.core.normalization.adapters.lever import LeverNormalizer
from radar_vagas.core.normalization.adapters.registry import NormalizationAdapterRegistry
from radar_vagas.core.normalization.adapters.remotive import RemotiveNormalizer
from radar_vagas.core.normalization.taxonomy import TaxonomyManager
from radar_vagas.domain.canonical import (
    EmploymentType,
    RoleFamily,
    SeniorityLevel,
    WorkArrangement,
)


def test_greenhouse_adapter_normalization():
    payload = {
        "id": 12345,
        "title": "Senior Data Engineer (Remote)",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
        "content": "<p>Build data pipelines using Python and dbt in US.</p>",
        "location": {"name": "Remote - United States"},
        "updated_at": "2026-07-26T12:00:00Z",
        "_board_identifier": "acme",
    }

    adapter = GreenhouseNormalizer()
    post = adapter.normalize_payload(
        payload=payload,
        observation_id="obs_gh_123",
        raw_content_hash="a" * 64,
        source_name="greenhouse_acme",
        cleaned_text="Build data pipelines using Python and dbt in US.",
    )

    assert post.normalized_job_id.startswith("norm_")
    assert post.source_job_id == "acme_12345"
    assert post.job_title == "Senior Data Engineer (Remote)"
    assert post.company_name == "acme"
    assert post.country_code == "US"
    assert post.work_arrangement == WorkArrangement.REMOTE
    assert post.role_family == RoleFamily.DATA_ENGINEER
    assert post.seniority == SeniorityLevel.SENIOR
    assert post.language == "en"
    assert len(post.provenance) >= 5


def test_lever_adapter_normalization():
    payload = {
        "id": "lever-abc-789",
        "text": "Lead Machine Learning Engineer",
        "hostedUrl": "https://jobs.lever.co/techcorp/lever-abc-789",
        "descriptionPlain": "Develop AI models in Germany",
        "categories": {"location": "Berlin, Germany", "commitment": "Full-time"},
        "createdAt": 1700000000000,
        "_company_identifier": "TechCorp Inc.",
    }

    adapter = LeverNormalizer()
    post = adapter.normalize_payload(
        payload=payload,
        observation_id="obs_lev_789",
        raw_content_hash="b" * 64,
        source_name="lever_techcorp",
    )

    assert post.company_name == "TechCorp"
    assert post.source_job_id == "TechCorp Inc._lever-abc-789"
    assert post.city == "Berlin"
    assert post.job_title == "Lead Machine Learning Engineer"
    assert post.employment_type == EmploymentType.FULL_TIME
    assert post.country_code == "DE"
    assert post.role_family == RoleFamily.MACHINE_LEARNING_ENGINEER
    assert post.seniority == SeniorityLevel.LEAD


def test_remotive_adapter_normalization():
    payload = {
        "id": 998877,
        "title": "Analytics Engineer",
        "company_name": "DataCo LLC",
        "url": "https://remotive.com/jobs/998877",
        "candidate_required_location": "Worldwide",
        "job_type": "full_time",
        "publication_date": "2026-07-20T10:00:00Z",
        "description": "SQL and dbt models",
    }

    adapter = RemotiveNormalizer()
    post = adapter.normalize_payload(
        payload=payload,
        observation_id="obs_rem_998",
        raw_content_hash="c" * 64,
        source_name="remotive",
    )

    assert post.company_name == "DataCo"
    assert post.work_arrangement == WorkArrangement.REMOTE
    assert post.role_family == RoleFamily.ANALYTICS_ENGINEER
    assert post.employment_type == EmploymentType.FULL_TIME


def test_arbeitnow_adapter_normalization():
    payload = {
        "slug": "data-analyst-berlin-1122",
        "title": "Junior Data Analyst",
        "company_name": "Berlin Analytics GmbH",
        "url": "https://arbeitnow.com/jobs/data-analyst-berlin-1122",
        "location": "Berlin",
        "remote": True,
        "created_at": 1700000000,
        "description": "Stelle fur Junior Data Analyst in Deutschland",
    }

    adapter = ArbeitnowNormalizer()
    post = adapter.normalize_payload(
        payload=payload,
        observation_id="obs_arb_112",
        raw_content_hash="d" * 64,
        source_name="arbeitnow",
    )

    assert post.company_name == "Berlin Analytics"
    assert post.job_title == "Junior Data Analyst"
    assert post.work_arrangement == WorkArrangement.REMOTE
    assert post.country_code == "DE"
    assert post.role_family == RoleFamily.DATA_ANALYST
    assert post.seniority == SeniorityLevel.JUNIOR
    assert post.language == "de"


def test_taxonomy_uses_token_boundaries_and_complete_epic5_categories():
    taxonomy = TaxonomyManager()

    assert taxonomy.infer_country_code("Remote") is None
    assert taxonomy.infer_country_code("Australia") is None
    assert taxonomy.infer_seniority("Staff Data Scientist") == SeniorityLevel.STAFF
    assert taxonomy.infer_seniority("Staffing Data Scientist") is None
    assert taxonomy.infer_seniority("Leadership analytics role") is None
    assert taxonomy.infer_seniority("Based at headquarters") is None
    assert taxonomy.infer_role_family("Data Platform Engineer") == RoleFamily.DATA_PLATFORM_ENGINEER
    assert taxonomy.infer_role_family("Technical Data Analyst") == RoleFamily.TECHNICAL_DATA_ANALYST


def test_registry_requires_a_supported_delimited_source_name():
    registry = NormalizationAdapterRegistry()

    assert isinstance(registry.get_adapter("greenhouse_gitlab"), GreenhouseNormalizer)
    assert isinstance(registry.get_adapter("lever_spotify"), LeverNormalizer)
    with pytest.raises(ValueError, match="non-empty source identifier"):
        registry.get_adapter("")
    with pytest.raises(ValueError, match="No normalization adapter"):
        registry.get_adapter("cleverjobs")
