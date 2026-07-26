from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from radar_vagas.cli import main
from radar_vagas.domain.models import RunState


def test_cli_collect_success(tmp_path: Path):
    with (
        patch("radar_vagas.core.ingestion.ConnectorRunner") as mock_runner_cls,
        patch("radar_vagas.cli.get_active_sources") as mock_get_sources,
        patch("radar_vagas.cli.load_catalog"),
    ):
        mock_runner = mock_runner_cls.return_value
        manifest = MagicMock()
        manifest.summary.run_id = "test_run"
        manifest.summary.duration_seconds = 1.0
        manifest.summary.total_sources_executed = 1

        src_summary = MagicMock()
        src_summary.state = RunState.success
        manifest.summary.sources = {"src": src_summary}

        mock_runner.run.return_value = manifest
        mock_get_sources.return_value = [MagicMock()]

        args = ["collect", "--catalog-dir", str(tmp_path)]
        assert main(args) == 0


def test_cli_collect_partial_failure(tmp_path: Path):
    with (
        patch("radar_vagas.core.ingestion.ConnectorRunner") as mock_runner_cls,
        patch("radar_vagas.cli.get_active_sources") as mock_get_sources,
        patch("radar_vagas.cli.load_catalog"),
    ):
        mock_runner = mock_runner_cls.return_value
        manifest = MagicMock()
        manifest.summary.run_id = "test_run"
        manifest.summary.duration_seconds = 1.0
        manifest.summary.total_sources_executed = 2

        src_ok = MagicMock()
        src_ok.state = RunState.success
        src_fail = MagicMock()
        src_fail.state = RunState.temporary_failure
        manifest.summary.sources = {"src_ok": src_ok, "src_fail": src_fail}

        mock_runner.run.return_value = manifest
        mock_get_sources.return_value = [MagicMock(), MagicMock()]

        args = ["collect", "--catalog-dir", str(tmp_path)]
        assert main(args) == 2


def test_cli_collect_total_failure(tmp_path: Path):
    with (
        patch("radar_vagas.core.ingestion.ConnectorRunner") as mock_runner_cls,
        patch("radar_vagas.cli.get_active_sources") as mock_get_sources,
        patch("radar_vagas.cli.load_catalog"),
    ):
        mock_runner = mock_runner_cls.return_value
        manifest = MagicMock()
        manifest.summary.run_id = "test_run"
        manifest.summary.duration_seconds = 1.0
        manifest.summary.total_sources_executed = 1

        src_summary = MagicMock()
        src_summary.state = RunState.temporary_failure
        manifest.summary.sources = {"src": src_summary}

        mock_runner.run.return_value = manifest
        mock_get_sources.return_value = [MagicMock()]

        args = ["collect", "--catalog-dir", str(tmp_path)]
        assert main(args) == 1


def test_cli_collect_invalid_limit(tmp_path: Path, capsys):
    args = ["collect", "--limit", "-1"]
    with pytest.raises(SystemExit) as exc_info:
        main(args)
    assert exc_info.value.code == 2
