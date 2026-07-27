import re
import tomllib
from pathlib import Path

from radar_vagas.domain.canonical import (
    EmploymentType,
    RoleFamily,
    SeniorityLevel,
    WorkArrangement,
)


class TaxonomyManager:
    """Loads and queries taxonomy definitions from TOML catalog files."""

    def __init__(self, taxonomy_dir: Path | None = None) -> None:
        self.taxonomy_dir = (
            taxonomy_dir
            or Path(__file__).resolve().parent.parent.parent.parent.parent
            / "catalogs"
            / "taxonomies"
        )
        self.role_family_rules: list[dict] = []
        self.seniority_rules: list[dict] = []
        self.work_arrangement_rules: list[dict] = []
        self.employment_type_rules: list[dict] = []
        self.country_code_mappings: list[dict] = []
        self._load_taxonomies()

    def _load_taxonomies(self) -> None:
        if not self.taxonomy_dir.exists():
            return

        role_path = self.taxonomy_dir / "role_families.toml"
        if role_path.exists():
            with role_path.open("rb") as f:
                data = tomllib.load(f)
                self.role_family_rules = data.get("rules", [])

        seniority_path = self.taxonomy_dir / "seniority.toml"
        if seniority_path.exists():
            with seniority_path.open("rb") as f:
                data = tomllib.load(f)
                self.seniority_rules = data.get("rules", [])

        work_path = self.taxonomy_dir / "work_arrangements.toml"
        if work_path.exists():
            with work_path.open("rb") as f:
                data = tomllib.load(f)
                self.work_arrangement_rules = data.get("rules", [])

        emp_path = self.taxonomy_dir / "employment_types.toml"
        if emp_path.exists():
            with emp_path.open("rb") as f:
                data = tomllib.load(f)
                self.employment_type_rules = data.get("rules", [])

        country_path = self.taxonomy_dir / "country_codes.toml"
        if country_path.exists():
            with country_path.open("rb") as f:
                data = tomllib.load(f)
                self.country_code_mappings = data.get("mappings", [])

    def infer_role_family(self, text: str | None) -> RoleFamily | None:
        if not text:
            return None
        text_lower = text.lower()
        for rule in self.role_family_rules:
            for kw in rule.get("keywords", []):
                if self._keyword_matches(text_lower, kw):
                    try:
                        return RoleFamily(rule["role_family"])
                    except ValueError:
                        pass
        return None

    def infer_seniority(self, text: str | None) -> SeniorityLevel | None:
        if not text:
            return None
        text_lower = text.lower()
        for rule in self.seniority_rules:
            for kw in rule.get("keywords", []):
                if self._keyword_matches(text_lower, kw):
                    try:
                        return SeniorityLevel(rule["seniority"])
                    except ValueError:
                        pass
        return None

    def infer_work_arrangement(self, text: str | None) -> WorkArrangement | None:
        if not text:
            return None
        text_lower = text.lower()
        for rule in self.work_arrangement_rules:
            for kw in rule.get("keywords", []):
                if self._keyword_matches(text_lower, kw):
                    try:
                        return WorkArrangement(rule["work_arrangement"])
                    except ValueError:
                        pass
        return None

    def infer_employment_type(self, text: str | None) -> EmploymentType | None:
        if not text:
            return None
        text_lower = text.lower()
        for rule in self.employment_type_rules:
            for kw in rule.get("keywords", []):
                if self._keyword_matches(text_lower, kw):
                    try:
                        return EmploymentType(rule["employment_type"])
                    except ValueError:
                        pass
        return None

    def infer_country_code(self, text: str | None) -> str | None:
        if not text:
            return None
        text_lower = text.lower()
        for mapping in self.country_code_mappings:
            for kw in mapping.get("keywords", []):
                if self._keyword_matches(text_lower, kw):
                    return mapping["country_code"]
        return None

    def is_country_label(self, text: str) -> bool:
        """Return whether a location component names a country rather than a city."""
        text_lower = text.casefold()
        return any(
            self._keyword_matches(text_lower, label)
            for mapping in self.country_code_mappings
            for label in mapping.get("country_labels", [])
        )

    @staticmethod
    def _keyword_matches(text: str, keyword: str) -> bool:
        normalized_keyword = keyword.casefold()
        return (
            re.search(
                rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)",
                text,
            )
            is not None
        )
