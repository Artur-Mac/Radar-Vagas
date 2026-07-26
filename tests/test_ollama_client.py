"""Unit tests for Ollama diagnostic client (isolated from network/server)."""

import httpx

from radar_vagas.infrastructure.llm.ollama_client import OllamaClient


def test_ollama_client_offline_diagnostic() -> None:
    # Transport that raises ConnectionError
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Server offline")

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.Client(transport=transport)

    client = OllamaClient(
        base_url="http://localhost:11434",
        model_name="gemma4:26b",
        client=mock_client,
    )

    assert not client.is_server_available()
    assert client.list_models() == []

    diag = client.get_diagnostic()
    assert not diag.server_available
    assert not diag.model_installed
    assert diag.configured_model == "gemma4:26b"
    assert "NOT reachable" in diag.message


def test_ollama_client_online_model_installed() -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "gemma4:26b"},
                        {"name": "llama3.2:latest"},
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.Client(transport=transport)

    client = OllamaClient(
        base_url="http://localhost:11434",
        model_name="gemma4:26b",
        client=mock_client,
    )

    assert client.is_server_available()
    models = client.list_models()
    assert "gemma4:26b" in models
    assert "llama3.2" in models

    diag = client.get_diagnostic()
    assert diag.server_available
    assert diag.model_installed
    assert "INSTALLED" in diag.message


def test_ollama_client_online_model_missing() -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "llama3.2:latest"}]},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.Client(transport=transport)

    client = OllamaClient(
        base_url="http://localhost:11434",
        model_name="gemma4:26b",
        client=mock_client,
    )

    assert client.is_server_available()
    diag = client.get_diagnostic()
    assert diag.server_available
    assert not diag.model_installed
    assert "NOT found" in diag.message
