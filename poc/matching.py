"""Candidate Profile Matching and Ranking Module for PoC."""

from pydantic import BaseModel

from poc.schema import CanonicalJob, LLMEnrichmentResult


class CandidateProfile(BaseModel):
    name: str = "Data Engineer -> DS/ML Transition"
    target_roles: list[str] = [
        "data_engineering",
        "analytics_engineering",
        "data_science",
        "machine_learning",
        "mlops",
        "ai_engineering",
    ]
    target_seniorities: list[str] = ["junior", "mid_level", "entry_level"]
    current_skills: list[str] = [
        "python",
        "sql",
        "azure",
        "databricks",
        "power bi",
        "git",
        "spark",
        "pyspark",
        "data lake",
        "data factory",
    ]
    learning_goals: list[str] = [
        "machine learning",
        "deep learning",
        "scikit-learn",
        "tensorflow",
        "pytorch",
        "mlops",
        "llm",
    ]
    accepts_remote: bool = True


class MatchScore(BaseModel):
    overall_score: float  # 0.0 to 100.0
    role_score: float
    seniority_score: float
    skill_match_score: float
    location_score: float
    matching_skills: list[str]
    missing_skills: list[str]
    reasoning: str


class JobMatcher:
    """Calculates relevance match score between candidate profile and enriched job."""

    def __init__(self, profile: CandidateProfile | None = None):
        self.profile = profile or CandidateProfile()

    def evaluate(self, job: CanonicalJob, enrichment: LLMEnrichmentResult) -> MatchScore:
        # 1. Role Family Match (Weight: 30%)
        if enrichment.role_family in self.profile.target_roles:
            role_score = 100.0
        else:
            role_score = 20.0

        # 2. Seniority Match (Weight: 25%)
        if enrichment.seniority in self.profile.target_seniorities:
            seniority_score = 100.0
        elif enrichment.seniority == "senior":
            seniority_score = 40.0
        elif enrichment.seniority == "unknown":
            seniority_score = 70.0
        else:
            seniority_score = 10.0

        # 3. Skill Overlap Match (Weight: 35%)
        extracted_tech = [s.name.casefold().strip() for s in enrichment.technical_skills]
        current_skills = {skill.casefold().strip() for skill in self.profile.current_skills}
        matching = []
        missing = []

        for tech in extracted_tech:
            if tech in current_skills:
                matching.append(tech)
            else:
                missing.append(tech)

        if extracted_tech:
            skill_match_score = (len(matching) / len(extracted_tech)) * 100.0
        else:
            skill_match_score = 50.0

        # 4. Work Arrangement & Location (Weight: 10%)
        if job.work_arrangement == "remote":
            location_score = 100.0
        elif job.work_arrangement == "hybrid":
            location_score = 75.0
        else:
            location_score = 50.0

        # Overall Score
        overall = (
            (role_score * 0.30)
            + (seniority_score * 0.25)
            + (skill_match_score * 0.35)
            + (location_score * 0.10)
        )

        reasoning = (
            f"Role: {enrichment.role_family} ({role_score:.0f}%), "
            f"Seniority: {enrichment.seniority} ({seniority_score:.0f}%), "
            f"Skill Match: {len(matching)}/{len(extracted_tech)} ({skill_match_score:.0f}%)"
        )

        return MatchScore(
            overall_score=round(overall, 1),
            role_score=role_score,
            seniority_score=seniority_score,
            skill_match_score=round(skill_match_score, 1),
            location_score=location_score,
            matching_skills=matching,
            missing_skills=missing,
            reasoning=reasoning,
        )
