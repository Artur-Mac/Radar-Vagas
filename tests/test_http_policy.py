"""Tests for HTTP policy and polite request handling."""

import httpx
import pytest

from radar_vagas.infrastructure.http import (
    HttpPolicy,
    create_http_client,
    polite_get,
)


def test_http_policy_defaults() -> None:
    policy = HttpPolicy()
    assert policy.timeout == 15.0
    assert policy.max_retries == 3
    assert policy.backoff_factor == 1.0
    assert policy.rate_limit_delay == 1.0
    assert policy.user_agent == "RadarVagas/0.1 (+https://github.com/radar-vagas)"


def test_create_http_client_uses_policy_timeout() -> None:
    policy = HttpPolicy(timeout=5.0)
    client = create_http_client(policy)
    assert client.timeout.read == 5.0
    client.close()


def test_polite_get_success_on_first_attempt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=0.01, rate_limit_delay=0.01)
    with httpx.Client(transport=transport) as client:
        response = polite_get(client, "https://api.example.com/test", policy=policy)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_polite_get_retries_on_429_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=0.01, rate_limit_delay=0.01)
    with httpx.Client(transport=transport) as client:
        response = polite_get(client, "https://api.example.com/test", policy=policy)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2


def test_polite_get_retries_on_500_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"error": "server error"})
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=0.01, rate_limit_delay=0.01)
    with httpx.Client(transport=transport) as client:
        response = polite_get(client, "https://api.example.com/test", policy=policy)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2


def test_polite_get_raises_after_max_retries_exhausted() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": "service unavailable"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=0.01, rate_limit_delay=0.01)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            polite_get(client, "https://api.example.com/test", policy=policy)
        assert exc_info.value.response.status_code == 503
        assert attempts == 3


def test_polite_get_does_not_retry_on_404() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=0.01, rate_limit_delay=0.01)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            polite_get(client, "https://api.example.com/test", policy=policy)
        assert exc_info.value.response.status_code == 404
        assert attempts == 1


def test_polite_get_retries_on_connect_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("Connection failed")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=0.01, rate_limit_delay=0.01)
    with httpx.Client(transport=transport) as client:
        response = polite_get(client, "https://api.example.com/test", policy=policy)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2
