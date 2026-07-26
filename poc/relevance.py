"""High-precision relevance gate for Data and AI job titles."""

import re
from dataclasses import dataclass

from poc.schema import CanonicalJob

TARGET_TITLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("analytics_engineering", re.compile(r"\banalytics?\s+engineer(?:ing)?\b", re.IGNORECASE)),
    ("data_engineering", re.compile(r"\bdata\s+engineer(?:ing)?\b", re.IGNORECASE)),
    ("data_science", re.compile(r"\bdata\s+scien(?:ce|tist)s?\b", re.IGNORECASE)),
    (
        "machine_learning",
        re.compile(
            r"\b(?:machine\s+learning|ml)\s+(?:engineer|scientist|developer)s?\b", re.IGNORECASE
        ),
    ),
    ("mlops", re.compile(r"\bml[\s-]?ops\b", re.IGNORECASE)),
    (
        "ai_engineering",
        re.compile(
            r"\b(?:ai|artificial\s+intelligence)\s+(?:engineer|architect|developer)s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "data_platform",
        re.compile(
            r"\b(?:data\s+(?:platform|infrastructure|reliability|quality)|"
            r"(?:etl|database))\s+(?:engineer|architect|developer)s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "business_intelligence",
        re.compile(
            r"\b(?:business\s+intelligence|bi)\s+(?:engineer|developer|analyst|consultant)s?\b",
            re.IGNORECASE,
        ),
    ),
    ("data_analytics", re.compile(r"\b(?:data|analytics)\s+analysts?\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class RelevanceDecision:
    """Explainable outcome from the deterministic relevance gate."""

    is_relevant: bool
    role_hint: str | None = None
    matched_text: str | None = None


class JobRelevanceFilter:
    """Keep only titles that explicitly describe an in-scope Data or AI role."""

    def evaluate(self, job: CanonicalJob) -> RelevanceDecision:
        title = job.title_normalized or job.title_raw
        for role_hint, pattern in TARGET_TITLE_PATTERNS:
            match = pattern.search(title)
            if match:
                return RelevanceDecision(
                    is_relevant=True,
                    role_hint=role_hint,
                    matched_text=match.group(0),
                )
        return RelevanceDecision(is_relevant=False)

    def filter(self, jobs: list[CanonicalJob]) -> list[CanonicalJob]:
        return [job for job in jobs if self.evaluate(job).is_relevant]
