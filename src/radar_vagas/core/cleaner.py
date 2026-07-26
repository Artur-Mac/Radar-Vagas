"""Deterministic text cleaning service for raw job descriptions."""

import html
import json
import re
import uuid
from datetime import UTC, datetime

from radar_vagas.domain.models import CleanedSourceText

_BLOCK_TAGS_PATTERN = re.compile(
    r"<(?:p|br|div|li|tr|h1|h2|h3|h4|h5|h6|article|section|header|footer|table)[^>]*>",
    re.IGNORECASE,
)
_ALL_TAGS_PATTERN = re.compile(r"<[^>]+>")
_MULTIPLE_NEWLINES_PATTERN = re.compile(r"\n{3,}")
_MULTIPLE_SPACES_PATTERN = re.compile(r"[ \t]+")


def clean_html_text(raw_text: str) -> str:
    """Clean HTML markup and entity encodings deterministically into plain text."""
    if not raw_text or not raw_text.strip():
        return ""

    # Unescape HTML entities (e.g. &amp;, &lt;, &nbsp;)
    text = html.unescape(raw_text)

    # Insert newline before block-level elements so words don't join together
    text = _BLOCK_TAGS_PATTERN.sub("\n", text)

    # Strip remaining HTML tags
    text = _ALL_TAGS_PATTERN.sub("", text)

    # Normalize whitespace per line
    lines = [line.strip() for line in text.splitlines()]

    # Collapse multiple empty lines
    cleaned = "\n".join(lines)
    cleaned = _MULTIPLE_NEWLINES_PATTERN.sub("\n\n", cleaned)
    cleaned = _MULTIPLE_SPACES_PATTERN.sub(" ", cleaned)

    return cleaned.strip()


def extract_description(raw_payload: str) -> str | None:
    """Extract raw description text from a raw payload string (JSON or plain text)."""
    if not raw_payload or not raw_payload.strip():
        return None

    try:
        data = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        # Plain text description
        return raw_payload.strip()

    if not isinstance(data, dict):
        return None

    # Priority field extraction for standard job sources
    candidate_fields = [
        "description",
        "content",  # Greenhouse
        "descriptionPlain",  # Lever
        "descriptionHtml",
        "details",
        "body",
        "text",
    ]

    for field in candidate_fields:
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None


class TextCleaner:
    """Service to create deterministic CleanedSourceText artifacts from observations."""

    def __init__(
        self,
        transformation_name: str = "default_html_cleaner",
        transformation_version: str = "0.1.0",
    ) -> None:
        self.transformation_name = transformation_name
        self.transformation_version = transformation_version

    def clean_observation_payload(
        self,
        observation_id: str,
        raw_content_hash: str,
        raw_payload: str,
    ) -> CleanedSourceText | None:
        """Derive a CleanedSourceText object from observation raw payload if description exists."""
        raw_desc = extract_description(raw_payload)
        if not raw_desc:
            return None

        cleaned = clean_html_text(raw_desc)
        if not cleaned:
            return None

        cleaned_id = f"clean_{uuid.uuid5(uuid.NAMESPACE_URL, f'{observation_id}:{self.transformation_name}:{self.transformation_version}').hex[:12]}"

        return CleanedSourceText(
            cleaned_id=cleaned_id,
            observation_id=observation_id,
            raw_content_hash=raw_content_hash,
            transformation_name=self.transformation_name,
            transformation_version=self.transformation_version,
            cleaned_text=cleaned,
            created_at=datetime.now(UTC),
        )
