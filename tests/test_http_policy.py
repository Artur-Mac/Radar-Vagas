"""Tests for HTTP policy and polite request handling."""

from unittest.mock import MagicMock

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
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        response = polite_get(
            client,
            "https://api.example.com/test",
            policy=policy,
            sleep_fn=mock_sleep,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_sleep.assert_not_called()


def test_polite_get_retries_on_429_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=1.0, rate_limit_delay=1.0)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        response = polite_get(
            client,
            "https://api.example.com/test",
            policy=policy,
            sleep_fn=mock_sleep,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2
        mock_sleep.assert_called_once_with(1.0)


def test_polite_get_respects_retry_after_header() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "5.5"},
                json={"error": "rate limited"},
            )
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=1.0, rate_limit_delay=1.0)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        response = polite_get(
            client,
            "https://api.example.com/test",
            policy=policy,
            sleep_fn=mock_sleep,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2
        mock_sleep.assert_called_once_with(5.5)


def test_polite_get_retries_on_500_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"error": "server error"})
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=1.0, rate_limit_delay=1.0)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        response = polite_get(
            client,
            "https://api.example.com/test",
            policy=policy,
            sleep_fn=mock_sleep,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2
        mock_sleep.assert_called_once_with(1.0)


def test_polite_get_raises_after_max_retries_exhausted() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": "service unavailable"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=1.0, rate_limit_delay=1.0)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            polite_get(
                client,
                "https://api.example.com/test",
                policy=policy,
                sleep_fn=mock_sleep,
            )
        assert exc_info.value.response.status_code == 503
        assert attempts == 3
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1.0
        assert mock_sleep.call_args_list[1][0][0] == 2.0


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 405, 501])
def test_polite_get_does_not_retry_non_retryable_status_codes(status_code: int) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code, json={"error": "client error"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            polite_get(
                client,
                "https://api.example.com/test",
                policy=policy,
                sleep_fn=mock_sleep,
            )
        assert exc_info.value.response.status_code == status_code
        assert attempts == 1
        mock_sleep.assert_not_called()


def test_polite_get_retries_on_connect_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("Connection failed")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=1.0, rate_limit_delay=1.0)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        response = polite_get(
            client,
            "https://api.example.com/test",
            policy=policy,
            sleep_fn=mock_sleep,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2
        mock_sleep.assert_called_once_with(1.0)


def test_polite_get_retries_on_timeout_exception() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.TimeoutException("Read timed out")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3, backoff_factor=1.0, rate_limit_delay=1.0)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        response = polite_get(
            client,
            "https://api.example.com/test",
            policy=policy,
            sleep_fn=mock_sleep,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert attempts == 2
        mock_sleep.assert_called_once_with(1.0)


def test_polite_get_raises_connect_error_when_retries_exhausted() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("Connection failed")

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.ConnectError):
            polite_get(
                client,
                "https://api.example.com/test",
                policy=policy,
                sleep_fn=mock_sleep,
            )
        assert attempts == 3
        assert mock_sleep.call_count == 2


def test_polite_get_raises_timeout_exception_when_retries_exhausted() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("Read timed out")

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=3)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.TimeoutException):
            polite_get(
                client,
                "https://api.example.com/test",
                policy=policy,
                sleep_fn=mock_sleep,
            )
        assert attempts == 3
        assert mock_sleep.call_count == 2


def test_polite_get_sanitizes_logs(caplog: pytest.LogCaptureFixture) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    policy = HttpPolicy(max_retries=2)
    mock_sleep = MagicMock()
    with httpx.Client(transport=transport) as client, caplog.at_level("DEBUG", logger="radar_vagas.infrastructure.http"):
            polite_get(
                client,
                "https://user:secretpass@api.example.com/search?api_key=supersecret123",
                policy=policy,
                sleep_fn=mock_sleep,
            )

    rv_logs = "\n".join(r.getMessage() for r in caplog.records if r.name == "radar_vagas.http")
    assert "supersecret123" not in rv_logs
    assert "secretpass" not in rv_logs
    assert "api.example.com/search" in rv_logs


