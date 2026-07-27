import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from radar_vagas.core.normalization.taxonomy import TaxonomyManager
from radar_vagas.domain.canonical import (
    CanonicalJobPost,
    ConfidenceCategory,
    FieldProvenance,
)

_LEGAL_SUFFIXES_RE = re.compile(
    r"\s+(?:Inc|LLC|GmbH|Ltd|S\.?A|Corp|Corporation|Co)\.?(?=\s|$)", re.IGNORECASE
)


class BaseNormalizationAdapter:
    """Base class for deterministic source adapters."""

    def __init__(
        self, taxonomy_manager: TaxonomyManager | None = None, rule_version: str = "1.0.0"
    ) -> None:
        self.taxonomy = taxonomy_manager or TaxonomyManager()
        self.rule_version = rule_version

    def normalize_company_name(
        self, raw_company: str | None
    ) -> tuple[str | None, str | None, ConfidenceCategory]:
        if not raw_company or not raw_company.strip():
            return None, raw_company, ConfidenceCategory.LOW
        cleaned = _LEGAL_SUFFIXES_RE.sub("", raw_company.strip()).strip()
        confidence = (
            ConfidenceCategory.HIGH if cleaned == raw_company.strip() else ConfidenceCategory.MEDIUM
        )
        return cleaned, raw_company, confidence

    def normalize_job_title(
        self, raw_title: str | None
    ) -> tuple[str | None, str | None, ConfidenceCategory]:
        if not raw_title or not raw_title.strip():
            return None, raw_title, ConfidenceCategory.LOW
        cleaned = re.sub(r"\s+", " ", raw_title).strip()
        return cleaned, raw_title, ConfidenceCategory.HIGH

    def normalize_url(
        self, raw_url: str | None
    ) -> tuple[str | None, str | None, ConfidenceCategory]:
        if not raw_url or not raw_url.strip():
            return None, raw_url, ConfidenceCategory.LOW
        raw_url = raw_url.strip()
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None, raw_url, ConfidenceCategory.LOW
        return raw_url, raw_url, ConfidenceCategory.HIGH

    def normalized_job_id(
        self,
        source_name: str,
        source_job_id: str,
        observation_id: str,
    ) -> str:
        """Create a stable ID for one observation and normalization rule version."""
        identity = (
            f"{source_name}\0{source_job_id}\0{observation_id}\0{self.rule_version}"
        ).encode()
        return f"norm_{hashlib.sha256(identity).hexdigest()[:24]}"

    def source_job_id_from_payload(self, payload: dict[str, Any]) -> str:
        """Return the exact source identity represented by a raw payload."""
        payload_id = payload.get("id")
        if payload_id is None or str(payload_id) == "":
            raise ValueError("Payload is missing its source job ID")
        return str(payload_id)

    def normalize_location(
        self, raw_location: str | None
    ) -> tuple[str | None, str | None, str | None]:
        """Conservatively split a location into city, region, and country."""
        if not raw_location:
            return None, None, None

        country_code = self.taxonomy.infer_country_code(raw_location)
        parts = [part.strip() for part in raw_location.split(",") if part.strip()]
        meaningful_parts = [
            part
            for part in parts
            if not self.taxonomy.infer_work_arrangement(part)
            and part.casefold() not in {"worldwide", "anywhere", "global"}
            and not self.taxonomy.is_country_label(part)
        ]
        city = meaningful_parts[0] if meaningful_parts else None
        state_or_region = meaningful_parts[1] if len(meaningful_parts) > 1 else None
        return city, state_or_region, country_code

    def detect_language(self, text: str | None) -> str | None:
        if not text:
            return None
        text_lower = text.lower()
        if any(w in text_lower for w in ("dados", "vaga", "engenheiro", "cientista", "trabalho")):
            return "pt"
        if any(w in text_lower for w in ("datos", "trabajo")):
            return "es"
        if any(w in text_lower for w in ("daten", "stelle", "deutschland", "für ", "fur ")):
            return "de"
        if any(w in text_lower for w in ("data", "engineer", "remote", "developer", "senior")):
            return "en"
        return None

    def add_provenance(
        self,
        prov_list: list[FieldProvenance],
        normalized_job_id: str,
        observation_id: str,
        field_name: str,
        original_value: Any,
        normalized_value: Any,
        rule_name: str,
        confidence: ConfidenceCategory = ConfidenceCategory.HIGH,
    ) -> None:
        provenance_identity = (
            f"{normalized_job_id}\0{observation_id}\0{field_name}\0{self.rule_version}"
        ).encode()
        prov_list.append(
            FieldProvenance(
                provenance_id=f"prov_{hashlib.sha256(provenance_identity).hexdigest()[:24]}",
                normalized_job_id=normalized_job_id,
                observation_id=observation_id,
                field_name=field_name,
                original_value=str(original_value) if original_value is not None else None,
                normalized_value=str(normalized_value) if normalized_value is not None else None,
                extraction_rule=rule_name,
                rule_version=self.rule_version,
                confidence=confidence,
            )
        )

    def add_location_provenance(
        self,
        prov_list: list[FieldProvenance],
        normalized_job_id: str,
        observation_id: str,
        raw_location: str | None,
        city: str | None,
        state_or_region: str | None,
    ) -> None:
        for field_name, normalized_value in (
            ("city", city),
            ("state_or_region", state_or_region),
        ):
            self.add_provenance(
                prov_list,
                normalized_job_id,
                observation_id,
                field_name,
                raw_location,
                normalized_value,
                "rule_location_components",
                ConfidenceCategory.MEDIUM if normalized_value else ConfidenceCategory.LOW,
            )

    def normalize_payload(
        self,
        payload: dict[str, Any],
        observation_id: str,
        raw_content_hash: str,
        source_name: str,
        source_job_id: str | None = None,
        cleaned_id: str | None = None,
        cleaned_text: str | None = None,
    ) -> CanonicalJobPost:
        raise NotImplementedError
