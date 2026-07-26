"""Unit tests for the source catalog TOML loader and filter utilities."""

from pathlib import Path

import pytest

from radar_vagas.domain.models import SourceConfig, SourceType
from radar_vagas.sources.catalog import (
    get_active_sources,
    load_catalog,
    load_catalog_file,
)


def test_load_catalog_file_parses_valid_toml(tmp_path: Path) -> None:
    """Verify load_catalog_file parses a valid TOML file into SourceConfig objects."""
    toml_content = """
    [[sources]]
    name = "Remotive API"
    source_type = "aggregator_api"
    base_url = "https://remotive.com/api/remote-jobs"
    active = true
    board_identifier = "remotive_board"
    company_identifier = "remotive_co"
    request_timeout = 10.0
    max_retries = 2
    rate_limit_delay = 0.5
    description = "Remotive job catalog source"
    career_url = "https://remotive.com"
    """
    catalog_file = tmp_path / "valid_catalog.toml"
    catalog_file.write_text(toml_content, encoding="utf-8")

    configs = load_catalog_file(catalog_file)

    assert len(configs) == 1
    config = configs[0]
    assert config.name == "Remotive API"
    assert config.source_type == SourceType.aggregator_api
    assert str(config.base_url) == "https://remotive.com/api/remote-jobs"
    assert config.active is True
    assert config.board_identifier == "remotive_board"
    assert config.company_identifier == "remotive_co"
    assert config.request_timeout == 10.0
    assert config.max_retries == 2
    assert config.rate_limit_delay == 0.5
    assert config.description == "Remotive job catalog source"
    assert config.career_url == "https://remotive.com"


def test_load_catalog_file_missing_file_raises(tmp_path: Path) -> None:
    """Verify load_catalog_file raises FileNotFoundError for non-existent file path."""
    non_existent = tmp_path / "non_existent_catalog.toml"

    with pytest.raises(FileNotFoundError):
        load_catalog_file(non_existent)


def test_load_catalog_file_missing_sources_key_raises(tmp_path: Path) -> None:
    """Verify load_catalog_file raises ValueError if TOML is missing [[sources]] table."""
    toml_content = """
    title = "Invalid Catalog"
    description = "Missing sources key"
    """
    catalog_file = tmp_path / "missing_sources.toml"
    catalog_file.write_text(toml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="missing the \\[\\[sources\\]\\] table"):
        load_catalog_file(catalog_file)


def test_load_catalog_file_rejects_invalid_entries(tmp_path: Path) -> None:
    """Verify invalid entries fail validation instead of disappearing silently."""
    toml_content = """
    [[sources]]
    name = "Valid Greenhouse"
    source_type = "ats_greenhouse"
    base_url = "https://boards.greenhouse.io"

    [[sources]]
    name = "Invalid Entry Missing Base Url"
    source_type = "ats_lever"

    [[sources]]
    name = "Valid Lever"
    source_type = "ats_lever"
    base_url = "https://jobs.lever.co"
    """
    catalog_file = tmp_path / "mixed_catalog.toml"
    catalog_file.write_text(toml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid source entries"):
        load_catalog_file(catalog_file)


def test_load_catalog_rejects_duplicate_names(tmp_path: Path) -> None:
    """Source names are stable identifiers and must be unique."""
    (tmp_path / "one.toml").write_text(
        '[[sources]]\nname="duplicate"\nsource_type="aggregator_api"\n'
        'base_url="https://example.com/one"\n',
        encoding="utf-8",
    )
    (tmp_path / "two.toml").write_text(
        '[[sources]]\nname="duplicate"\nsource_type="aggregator_api"\n'
        'base_url="https://example.com/two"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate source names"):
        load_catalog(tmp_path)


def test_load_catalog_loads_all_toml_files_in_directory(tmp_path: Path) -> None:
    """Verify load_catalog loads and merges all .toml files in a directory."""
    catalog_dir = tmp_path / "catalog_dir"
    catalog_dir.mkdir()

    file1_content = """
    [[sources]]
    name = "Source 1"
    source_type = "ats_greenhouse"
    base_url = "https://boards.greenhouse.io/source1"
    """
    (catalog_dir / "01_sources.toml").write_text(file1_content, encoding="utf-8")

    file2_content = """
    [[sources]]
    name = "Source 2"
    source_type = "ats_lever"
    base_url = "https://jobs.lever.co/source2"
    """
    (catalog_dir / "02_sources.toml").write_text(file2_content, encoding="utf-8")

    configs = load_catalog(catalog_dir)

    assert len(configs) == 2
    assert configs[0].name == "Source 1"
    assert configs[1].name == "Source 2"


def test_load_catalog_empty_directory(tmp_path: Path) -> None:
    """Verify load_catalog returns an empty list for a directory with no .toml files."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    configs = load_catalog(empty_dir)

    assert configs == []


def test_get_active_sources_filters_inactive() -> None:
    """Verify get_active_sources returns only sources where active is True."""
    configs = [
        SourceConfig(
            name="Active Greenhouse",
            source_type=SourceType.ats_greenhouse,
            base_url="https://boards.greenhouse.io/active",
            active=True,
        ),
        SourceConfig(
            name="Inactive Lever",
            source_type=SourceType.ats_lever,
            base_url="https://jobs.lever.co/inactive",
            active=False,
        ),
        SourceConfig(
            name="Active Remotive",
            source_type=SourceType.aggregator_api,
            base_url="https://remotive.com/api/remote-jobs",
            active=True,
        ),
    ]

    active_configs = get_active_sources(configs)

    assert len(active_configs) == 2
    assert [c.name for c in active_configs] == ["Active Greenhouse", "Active Remotive"]
