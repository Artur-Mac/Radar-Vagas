"""Unit tests for TextCleaner service."""

from radar_vagas.core.cleaner import TextCleaner, clean_html_text, extract_description


def test_clean_html_text_decodes_entities_and_strips_tags():
    html_input = "<h1>Data Engineer</h1><p>We are hiring &amp; looking for <b>Python</b> developers.</p><ul><li>ETL</li><li>SQL</li></ul>"
    cleaned = clean_html_text(html_input)

    assert "Data Engineer" in cleaned
    assert "We are hiring & looking for Python developers." in cleaned
    assert "ETL" in cleaned
    assert "SQL" in cleaned
    assert "<" not in cleaned
    assert "&amp;" not in cleaned


def test_clean_html_text_empty():
    assert clean_html_text("") == ""
    assert clean_html_text("   ") == ""


def test_extract_description_json_and_plain():
    payload_json = '{"title": "Data Scientist", "description": "<p>Build ML models</p>"}'
    assert extract_description(payload_json) == "<p>Build ML models</p>"

    payload_greenhouse = '{"title": "MLE", "content": "<p>Greenhouse content</p>"}'
    assert extract_description(payload_greenhouse) == "<p>Greenhouse content</p>"

    payload_plain = "Plain text job description without JSON"
    assert extract_description(payload_plain) == payload_plain


def test_extract_description_missing():
    payload_no_desc = '{"title": "No description field"}'
    assert extract_description(payload_no_desc) is None


def test_text_cleaner_reproducible_and_versioned():
    cleaner = TextCleaner(transformation_name="test_cleaner", transformation_version="1.0.0")

    result = cleaner.clean_observation_payload(
        observation_id="obs_123",
        raw_content_hash="a" * 64,
        raw_payload='{"description": "<p>Test <b>description</b></p>"}',
    )

    assert result is not None
    assert result.observation_id == "obs_123"
    assert result.cleaned_text == "Test description"
    assert result.transformation_name == "test_cleaner"
    assert result.transformation_version == "1.0.0"

    # Verify reproducibility
    result2 = cleaner.clean_observation_payload(
        observation_id="obs_123",
        raw_content_hash="a" * 64,
        raw_payload='{"description": "<p>Test <b>description</b></p>"}',
    )
    assert result2.cleaned_id == result.cleaned_id
    assert result2.cleaned_text == result.cleaned_text
