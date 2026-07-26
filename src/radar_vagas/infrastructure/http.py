"""Centralised HTTP policies for polite, resilient API requests."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

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


def polite_get(
    client: httpx.Client,
    url: str,
    *,
    policy: HttpPolicy | None = None,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    """Perform a GET request with retry, exponential backoff, and rate limiting.

    Retries are attempted only for status codes in ``_RETRYABLE_STATUS_CODES``.
    Connection and timeout errors are also retried.

    Raises
    ------
    httpx.HTTPStatusError
        When the final response has a non-2xx status after all retries.
    httpx.ConnectError
        When the server is unreachable after all retries.
    """
    policy = policy or HttpPolicy()
    metrics = _RequestMetrics()

    for attempt in range(1, policy.max_retries + 1):
        metrics.attempts = attempt
        try:
            if attempt > 1 and policy.rate_limit_delay > 0:
                delay = policy.backoff_factor * (2 ** (attempt - 2))
                delay = max(delay, policy.rate_limit_delay)
                logger.debug("Backing off %.1fs before retry %d for %s", delay, attempt, url)
                time.sleep(delay)

            response = client.get(url, params=params)
            metrics.last_status = response.status_code

            if response.status_code < 400:
                return response

            if response.status_code not in _RETRYABLE_STATUS_CODES:
                # Non-retryable error — fail immediately.
                response.raise_for_status()

            logger.warning(
                "Retryable status %d from %s (attempt %d/%d)",
                response.status_code,
                url,
                attempt,
                policy.max_retries,
            )

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "Connection error on %s (attempt %d/%d): %s",
                url,
                attempt,
                policy.max_retries,
                exc,
            )
            metrics.errors.append(str(exc))
            if attempt == policy.max_retries:
                raise

    # All retries exhausted with retryable status codes.
    msg = (
        f"Request to {url} failed after {policy.max_retries} attempts "
        f"(last status: {metrics.last_status})"
    )
    raise httpx.HTTPStatusError(
        msg,
        request=httpx.Request("GET", url),
        response=httpx.Response(metrics.last_status),
    )
