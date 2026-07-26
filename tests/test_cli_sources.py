"""Unit tests for 'sources' CLI command."""

from pathlib import Path

import pytest

from radar_vagas.cli import main


def test_cli_sources_lists_all(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    toml_file = tmp_path / "sources.toml"
    toml_file.write_text(
        """
[[sources]]
name = "test_source_active"
source_type = "aggregator_api"
base_url = "https://example.com/api"
active = true

[[sources]]
name = "test_source_inactive"
source_type = "ats_greenhouse"
base_url = "https://boards-api.greenhouse.io/v1/boards"
board_identifier = "testboard"
active = false
"""
    )

    exit_code = main(["sources", "--catalog-dir", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "test_source_active" in captured.out
    assert "test_source_inactive" in captured.out
    assert "Total: 2 source(s)" in captured.out


def test_cli_sources_active_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    toml_file = tmp_path / "sources.toml"
    toml_file.write_text(
        """
[[sources]]
name = "active_source"
source_type = "aggregator_api"
base_url = "https://example.com/api"
active = true

[[sources]]
name = "inactive_source"
source_type = "aggregator_api"
base_url = "https://example.com/api"
active = false
"""
    )

    exit_code = main(["sources", "--catalog-dir", str(tmp_path), "--active-only"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "active_source" in captured.out
    assert "inactive_source" not in captured.out
    assert "Total: 1 source(s)" in captured.out


def test_cli_sources_missing_catalog_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    nonexistent = tmp_path / "nonexistent"
    exit_code = main(["sources", "--catalog-dir", str(nonexistent)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Catalog directory not found" in captured.out
