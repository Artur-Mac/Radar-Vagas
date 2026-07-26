"""Unit tests for Radar-Vagas CLI interface."""

import httpx

from radar_vagas.cli import main
from radar_vagas.infrastructure.llm.ollama_client import OllamaClient


def test_cli_info_command(capsys) -> None:
    exit_code = main(["info"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "RADAR-VAGAS CONFIGURATION" in captured.out
    assert "Environment:" in captured.out


def test_cli_doctor_command(capsys, monkeypatch) -> None:
    def offline_client(self: OllamaClient) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("offline", request=request)

        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(OllamaClient, "_get_http_client", offline_client)
    exit_code = main(["doctor"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "RADAR-VAGAS LOCAL DIAGNOSTIC REPORT" in captured.out
    assert "Server Available:" in captured.out
