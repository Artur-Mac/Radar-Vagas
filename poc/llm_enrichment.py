"""Local LLM Enrichment module using Ollama for PoC."""

import json
import re
import time

import httpx

from poc.schema import CanonicalJob, ExtractedSkill, LLMEnrichmentResult

SYSTEM_PROMPT = """You are a job market data extraction assistant.
Analyze the job description and extract structured JSON matching this exact schema:
{
  "role_family": "data_engineering" | "analytics_engineering" | "data_science" | "machine_learning" | "mlops" | "ai_engineering" | "data_platform" | "business_intelligence" | "other",
  "seniority": "internship" | "entry_level" | "junior" | "mid_level" | "senior" | "staff_lead" | "executive" | "unknown",
  "technical_skills": [
    {
      "name": "Python",
      "requirement_type": "required" | "preferred",
      "evidence": "Quote from text"
    }
  ],
  "soft_skills": ["Communication", "Teamwork"],
  "minimum_years_experience": 3,
  "education_required": false,
  "required_languages": ["English", "Portuguese"],
  "work_arrangement": "remote" | "hybrid" | "on_site" | "unknown",
  "summary": "Brief summary of the role"
}

RULES:
1. Return ONLY valid raw JSON. No markdown code blocks, no explanations.
2. Do NOT invent technologies not mentioned in the text.
3. Classify seniority based on explicit title/text (e.g. Senior -> senior, Lead -> staff_lead, Junior -> junior).
"""


class LLMEnricher:
    """Enriches job descriptions using local Ollama model."""

    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.2"):
        self.host = host
        self.model = model
        self.client = httpx.Client(timeout=60.0)

    def is_available(self) -> bool:
        """Check if Ollama server is reachable and model is available."""
        try:
            res = self.client.get(f"{self.host}/api/tags")
            if res.status_code == 200:
                models = {
                    str(model.get("name", "")).removesuffix(":latest")
                    for model in res.json().get("models", [])
                }
                return self.model.removesuffix(":latest") in models
        except (httpx.HTTPError, ValueError):
            return False
        return False

    def close(self) -> None:
        """Release the reusable HTTP connection pool."""
        self.client.close()

    def enrich(self, job: CanonicalJob) -> LLMEnrichmentResult:
        """Enrich a single canonical job."""
        start_time = time.time()

        prompt = f"Job Title: {job.title_raw}\nCompany: {job.company_raw}\nDescription:\n{job.description_clean[:2500]}"

        try:
            res = self.client.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "system": SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            elapsed = time.time() - start_time

            if res.status_code == 200:
                raw_response = res.json().get("response", "")
                parsed = json.loads(raw_response)

                # Parse technical skills
                raw_skills = parsed.get("technical_skills", [])
                tech_skills = []
                for s in raw_skills:
                    if isinstance(s, dict):
                        tech_skills.append(
                            ExtractedSkill(
                                name=s.get("name", ""),
                                requirement_type=s.get("requirement_type", "required"),
                                evidence=s.get("evidence"),
                            )
                        )
                    elif isinstance(s, str):
                        tech_skills.append(ExtractedSkill(name=s, requirement_type="required"))

                return LLMEnrichmentResult(
                    role_family=parsed.get("role_family", "other"),
                    seniority=parsed.get("seniority", "unknown"),
                    technical_skills=tech_skills,
                    soft_skills=parsed.get("soft_skills", []),
                    minimum_years_experience=parsed.get("minimum_years_experience"),
                    education_required=parsed.get("education_required", False),
                    required_languages=parsed.get("required_languages", []),
                    work_arrangement=parsed.get("work_arrangement", job.work_arrangement),
                    summary=parsed.get("summary", ""),
                    is_valid_json=True,
                    extraction_latency_seconds=elapsed,
                )
        except (httpx.HTTPError, TypeError, ValueError) as e:
            elapsed = time.time() - start_time
            print(f"Ollama enrichment failed/offline: {e}")

        # Rule-based fallback if LLM is offline or fails
        return self._heuristic_fallback(job, time.time() - start_time)

    def _heuristic_fallback(self, job: CanonicalJob, elapsed: float) -> LLMEnrichmentResult:
        """Deterministic heuristic fallback for PoC when Ollama is unavailable."""
        title_lower = job.title_raw.lower()
        desc_lower = job.description_clean.lower()

        # Role family
        if "data engineer" in title_lower or "data engineering" in title_lower:
            role_family = "data_engineering"
        elif "analytics engineer" in title_lower:
            role_family = "analytics_engineering"
        elif "data scientist" in title_lower or "data science" in title_lower:
            role_family = "data_science"
        elif "machine learning" in title_lower or "ml engineer" in title_lower:
            role_family = "machine_learning"
        elif "mlops" in title_lower:
            role_family = "mlops"
        elif "ai engineer" in title_lower:
            role_family = "ai_engineering"
        elif "bi" in title_lower or "business intelligence" in title_lower:
            role_family = "business_intelligence"
        else:
            role_family = "other"

        # Seniority
        if "senior" in title_lower or "sr" in title_lower:
            seniority = "senior"
        elif "lead" in title_lower or "staff" in title_lower or "principal" in title_lower:
            seniority = "staff_lead"
        elif "junior" in title_lower or "jr" in title_lower:
            seniority = "junior"
        elif "intern" in title_lower:
            seniority = "internship"
        else:
            seniority = "mid_level"

        # Common tech skills heuristic detection
        tech_keywords = [
            "python",
            "sql",
            "azure",
            "aws",
            "gcp",
            "databricks",
            "spark",
            "pyspark",
            "snowflake",
            "dbt",
            "kafka",
            "airflow",
            "docker",
            "kubernetes",
            "git",
            "power bi",
            "tableau",
            "postgresql",
            "duckdb",
        ]
        found_skills = []
        searchable_text = f"{title_lower}\n{desc_lower}"
        for kw in tech_keywords:
            pattern = rf"(?<![\w]){re.escape(kw)}(?![\w])"
            if re.search(pattern, searchable_text):
                found_skills.append(
                    ExtractedSkill(name=kw.capitalize(), requirement_type="required")
                )

        return LLMEnrichmentResult(
            role_family=role_family,
            seniority=seniority,
            technical_skills=found_skills,
            soft_skills=[],
            minimum_years_experience=None,
            education_required=False,
            required_languages=["English"] if "english" in desc_lower else [],
            work_arrangement=job.work_arrangement,
            summary=f"Role: {job.title_raw} at {job.company_raw}",
            is_valid_json=False,
            extraction_latency_seconds=elapsed,
        )
