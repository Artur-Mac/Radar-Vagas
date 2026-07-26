"""Regression tests for the PoC's highest-risk ranking inputs."""

from poc.connectors.base import balanced_sample
from poc.deduplication import Deduplicator
from poc.llm_enrichment import LLMEnricher
from poc.matching import JobMatcher
from poc.relevance import JobRelevanceFilter
from poc.schema import CanonicalJob, ExtractedSkill, LLMEnrichmentResult


def make_job(
    title: str,
    description: str = "",
    *,
    company: str = "Example",
    job_id: str = "test_1",
) -> CanonicalJob:
    return CanonicalJob(
        job_id=job_id,
        source_name="test",
        source_job_id=job_id,
        title_raw=title,
        title_normalized=title,
        company_raw=company,
        company_normalized=company,
        description_raw=description,
        description_clean=description,
    )


def make_enrichment(*skills: str) -> LLMEnrichmentResult:
    return LLMEnrichmentResult(
        role_family="data_engineering",
        seniority="mid_level",
        technical_skills=[ExtractedSkill(name=skill) for skill in skills],
    )


def test_relevance_gate_keeps_target_roles() -> None:
    relevance_filter = JobRelevanceFilter()

    assert relevance_filter.evaluate(make_job("Senior AI Engineer")).is_relevant
    assert relevance_filter.evaluate(make_job("Analytics Engineer II")).is_relevant
    assert relevance_filter.evaluate(make_job("Machine Learning Engineer")).is_relevant
    assert relevance_filter.evaluate(
        make_job("Data Infrastructure Engineer – Platform")
    ).is_relevant


def test_relevance_gate_rejects_general_roles_that_polluted_original_ranking() -> None:
    relevance_filter = JobRelevanceFilter()

    assert not relevance_filter.evaluate(make_job("Content Reviewer - United States")).is_relevant
    assert not relevance_filter.evaluate(
        make_job("Product Sales Specialist - Pet Health")
    ).is_relevant
    assert not relevance_filter.evaluate(make_job("Head of Marketing & Communications")).is_relevant
    assert not relevance_filter.evaluate(make_job("Product Manager - Data Platform")).is_relevant


def test_heuristic_skill_detection_respects_word_boundaries() -> None:
    enricher = LLMEnricher()
    job = make_job("Content Reviewer", "Review digital content and spark conversations.")

    result = enricher._heuristic_fallback(job, elapsed=0.0)

    skill_names = {skill.name.casefold() for skill in result.technical_skills}
    assert "git" not in skill_names
    assert "spark" in skill_names


def test_matcher_does_not_use_partial_skill_name_matches() -> None:
    score = JobMatcher().evaluate(
        make_job("Data Engineer"),
        make_enrichment("GitLab", "Python"),
    )

    assert score.matching_skills == ["python"]
    assert score.missing_skills == ["gitlab"]
    assert score.skill_match_score == 50.0


def test_blank_descriptions_are_not_all_deduplicated() -> None:
    deduplicator = Deduplicator()

    first = deduplicator.is_duplicate(make_job("Data Engineer", job_id="1"))
    second = deduplicator.is_duplicate(make_job("ML Engineer", company="Another", job_id="2"))

    assert first == (False, "")
    assert second == (False, "")


def test_balanced_sample_does_not_let_first_source_consume_limit() -> None:
    groups = [["a1", "a2", "a3"], ["b1", "b2"], ["c1"]]

    assert balanced_sample(groups, limit=5) == ["a1", "b1", "c1", "a2", "b2"]
