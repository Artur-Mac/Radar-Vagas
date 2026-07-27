from datetime import datetime
from typing import Any

from radar_vagas.core.normalization.adapters.base import BaseNormalizationAdapter
from radar_vagas.domain.canonical import (
    CanonicalJobPost,
    ConfidenceCategory,
    FieldProvenance,
)


class GreenhouseNormalizer(BaseNormalizationAdapter):
    """Deterministic adapter for Greenhouse ATS job postings."""

    def source_job_id_from_payload(self, payload: dict[str, Any]) -> str:
        payload_id = super().source_job_id_from_payload(payload)
        board_identifier = payload.get("_board_identifier")
        return f"{board_identifier}_{payload_id}" if board_identifier else payload_id

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
        payload_source_job_id = self.source_job_id_from_payload(payload)
        if source_job_id is not None and source_job_id != payload_source_job_id:
            raise ValueError(
                f"Greenhouse source job ID mismatch: expected {source_job_id}, "
                f"got {payload_source_job_id}"
            )
        source_job_id = source_job_id or payload_source_job_id
        norm_id = self.normalized_job_id(source_name, source_job_id, observation_id)
        provenance: list[FieldProvenance] = []

        raw_company = payload.get("company_name") or payload.get("_board_identifier")
        company, orig_comp, comp_conf = self.normalize_company_name(raw_company)
        self.add_provenance(
            provenance,
            norm_id,
            observation_id,
            "company_name",
            orig_comp,
            company,
            "rule_company_name",
            comp_conf,
        )

        raw_title = payload.get("title")
        title, orig_title, title_conf = self.normalize_job_title(raw_title)
        self.add_provenance(
            provenance,
            norm_id,
            observation_id,
            "job_title",
            orig_title,
            title,
            "rule_job_title",
            title_conf,
        )

        raw_url = payload.get("absolute_url")
        url, orig_url, url_conf = self.normalize_url(raw_url)
        self.add_provenance(
            provenance,
            norm_id,
            observation_id,
            "application_url",
            orig_url,
            url,
            "rule_application_url",
            url_conf,
        )

        loc_obj = payload.get("location")
        raw_loc = loc_obj.get("name") if isinstance(loc_obj, dict) else str(loc_obj or "")
        work_arr = self.taxonomy.infer_work_arrangement(
            raw_loc
        ) or self.taxonomy.infer_work_arrangement(title)
        self.add_provenance(
            provenance,
            norm_id,
            observation_id,
            "work_arrangement",
            raw_loc,
            work_arr,
            "rule_taxonomy_work_arrangement",
            ConfidenceCategory.HIGH if work_arr else ConfidenceCategory.LOW,
        )

        city, state_or_region, country = self.normalize_location(raw_loc)
        self.add_provenance(
            provenance,
            norm_id,
            observation_id,
            "country_code",
            raw_loc,
            country,
            "rule_taxonomy_country_code",
            ConfidenceCategory.HIGH if country else ConfidenceCategory.LOW,
        )
        self.add_location_provenance(
            provenance,
            norm_id,
            observation_id,
            raw_loc,
            city,
            state_or_region,
        )

        role_family = self.taxonomy.infer_role_family(title)
        self.add_provenance(
            provenance,
            norm_id,
            observation_id,
            "role_family",
            title,
            role_family,
            "rule_taxonomy_role_family",
            ConfidenceCategory.HIGH if role_family else ConfidenceCategory.LOW,
        )

        seniority = self.taxonomy.infer_seniority(title)
        self.add_provenance(
            provenance,
            norm_id,
            observation_id,
            "seniority",
            title,
            seniority,
            "rule_taxonomy_seniority",
            ConfidenceCategory.HIGH if seniority else ConfidenceCategory.LOW,
        )

        published_at = None
        raw_date = payload.get("updated_at")
        if raw_date:
            try:
                published_at = datetime.fromisoformat(str(raw_date))
            except ValueError:
                pass

        description = cleaned_text or payload.get("content")
        language = self.detect_language(description) or self.detect_language(title)

        return CanonicalJobPost(
            normalized_job_id=norm_id,
            source_name=source_name,
            source_job_id=source_job_id,
            observation_id=observation_id,
            raw_content_hash=raw_content_hash,
            cleaned_id=cleaned_id,
            company_name=company,
            job_title=title,
            location_raw=raw_loc or None,
            city=city,
            state_or_region=state_or_region,
            country_code=country,
            work_arrangement=work_arr,
            published_at=published_at,
            description=description,
            application_url=url,
            role_family=role_family,
            seniority=seniority,
            language=language,
            normalization_rule_version=self.rule_version,
            provenance=provenance,
        )
