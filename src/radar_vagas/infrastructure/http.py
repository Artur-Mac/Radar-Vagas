"""Centralised HTTP policies for polite, resilient API requests."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("radar_vagas.http")

# HTTP status codes that warrant a retry.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503})


@dataclass(frozen=True)
class HttpPolicy:
    """HTTP request policy: timeouts, retries, and rate limiting.

    Instances are immutable so they can be shared across connectors safely.
    """

    timeout: float = 15.0
    max_retries: int = 3
    backoff_factor: float = 1.0
    rate_limit_delay: float = 1.0
    user_agent: str = "RadarVagas/0.1 (+https://github.com/radar-vagas)"


@dataclass
class _RequestMetrics:
    """Internal bookkeeping for polite_get retry loop."""

    attempts: int = 0
    last_status: int = 0
    errors: list[str] = field(default_factory=list)


def create_http_client(policy: HttpPolicy | None = None) -> httpx.Client:
    """Create an ``httpx.Client`` pre-configured with the given policy."""
    policy = policy or HttpPolicy()
    return httpx.Client(
        timeout=policy.timeout,
        headers={"User-Agent": policy.user_agent},
        follow_redirects=True,
    )


def _sanitize_url(url: str) -> str:
    """Sanitize URL for logging by omitting user info, query parameters, and fragments."""
    try:
        parsed = urlparse(url)
        scheme = f"{parsed.scheme}://" if parsed.scheme else ""
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        path = parsed.path
        return f"{scheme}{host}{port}{path}"
    except ValueError:
        return "<invalid-url>"


def polite_get(
    client: httpx.Client,
    url: str,
    *,
    policy: HttpPolicy | None = None,
    params: dict[str, str] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Perform a GET request with retry, exponential backoff, and rate limiting.

    Retries are attempted only for status codes in ``_RETRYABLE_STATUS_CODES``.
    Connection and timeout errors are also retried.

    Raises
    ------
    httpx.HTTPStatusError
        When the response has a non-2xx status after all retries (or immediately if non-retryable).
    httpx.ConnectError
        When the server is unreachable after all retries.
    httpx.TimeoutException
        When the request times out after all retries.
    """
    policy = policy or HttpPolicy()
    metrics = _RequestMetrics()
    safe_url = _sanitize_url(url)
    next_delay: float | None = None

    for attempt in range(1, policy.max_retries + 1):
        metrics.attempts = attempt

        if attempt > 1:
            if next_delay is not None:
                delay = next_delay
                next_delay = None
            else:
                delay = policy.backoff_factor * (2 ** (attempt - 2))
                if policy.rate_limit_delay > 0:
                    delay = max(delay, policy.rate_limit_delay)

            if delay > 0:
                logger.debug(
                    "Backing off %.1fs before retry %d for %s",
                    delay,
                    attempt,
                    safe_url,
                )
                sleep_fn(delay)

        try:
            response = client.get(url, params=params)
            metrics.last_status = response.status_code

            if response.status_code < 400:
                return response

            if response.status_code not in _RETRYABLE_STATUS_CODES or attempt == policy.max_retries:
                response.raise_for_status()

            if response.status_code == 429 and "Retry-After" in response.headers:
                try:
                    parsed_retry_after = float(response.headers["Retry-After"])
                    if parsed_retry_after >= 0:
                        next_delay = parsed_retry_after
                    else:
                        next_delay = None
                except (ValueError, TypeError):
                    next_delay = None
            else:
                next_delay = None

            logger.warning(
                "Retryable status %d from %s (attempt %d/%d)",
                response.status_code,
                safe_url,
                attempt,
                policy.max_retries,
            )

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning(
                "Connection error on %s (attempt %d/%d): %s",
                safe_url,
                attempt,
                policy.max_retries,
                exc.__class__.__name__,
            )
            metrics.errors.append(str(exc))
            next_delay = None
            if attempt == policy.max_retries:
                raise
        except httpx.HTTPStatusError as exc:
            metrics.last_status = exc.response.status_code
            metrics.errors.append(str(exc))
            if (
                exc.response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt == policy.max_retries
            ):
                raise
            if exc.response.status_code == 429 and "Retry-After" in exc.response.headers:
                try:
                    parsed_retry_after = float(exc.response.headers["Retry-After"])
                    if parsed_retry_after >= 0:
                        next_delay = parsed_retry_after
                    else:
                        next_delay = None
                except (ValueError, TypeError):
                    next_delay = None
            else:
                next_delay = None
            logger.warning(
                "Retryable status %d from %s (attempt %d/%d)",
                exc.response.status_code,
                safe_url,
                attempt,
                policy.max_retries,
            )

    msg = (
        f"Request to {safe_url} failed after {policy.max_retries} attempts "
        f"(last status: {metrics.last_status})"
    )
    raise httpx.HTTPStatusError(
        msg,
        request=httpx.Request("GET", url),
        response=httpx.Response(metrics.last_status),
    )
