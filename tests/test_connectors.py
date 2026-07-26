"""Unit tests for job source connectors (Remotive, Arbeitnow, Greenhouse, Lever)."""

import httpx

from radar_vagas.connectors.arbeitnow import ArbeitnowConnector
from radar_vagas.connectors.greenhouse import GreenhouseConnector
from radar_vagas.connectors.lever import LeverConnector
from radar_vagas.connectors.remotive import RemotiveConnector
from radar_vagas.domain.models import RawJobRecord, SourceConfig, SourceType

# ---------------------------------------------------------------------------
# RemotiveConnector Tests
# ---------------------------------------------------------------------------


def test_remotive_fetch_success() -> None:
    config = SourceConfig(
        name="remotive_test",
        source_type=SourceType.aggregator_api,
        base_url="https://remotive.com/api/remote-jobs",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = RemotiveConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/remote-jobs"
        payload = {
            "jobs": [
                {
                    "id": 123,
                    "title": "Data Engineer",
                    "company_name": "TechCo",
                    "url": "https://remotive.com/jobs/123",
                    "description": "Build pipelines",
                    "candidate_required_location": "Worldwide",
                    "job_type": "full_time",
                    "publication_date": "2024-01-15T10:00:00",
                }
            ]
        }
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client, limit=10)
        assert result.source_name == "remotive_test"
        assert result.records_fetched == 1
        assert len(result.records) == 1
        assert result.records[0].source_job_id == "123"
        assert result.records[0].source_type == SourceType.aggregator_api
        assert result.records_failed == 0
        assert len(result.errors) == 0


def test_remotive_normalize() -> None:
    config = SourceConfig(
        name="remotive_test",
        source_type=SourceType.aggregator_api,
        base_url="https://remotive.com/api/remote-jobs",
    )
    connector = RemotiveConnector(config)
    raw_record = RawJobRecord(
        source_name="remotive_test",
        source_job_id="123",
        content_hash="hash123",
        raw_payload='{"id": 123, "title": "Data Engineer", "company_name": "TechCo", "url": "https://remotive.com/jobs/123", "description": "Build pipelines", "candidate_required_location": "Worldwide", "job_type": "full_time", "publication_date": "2024-01-15T10:00:00"}',
        source_url="https://remotive.com/jobs/123",
    )
    canonical = connector.normalize(raw_record)
    assert canonical.job_id == "remotive_123"
    assert canonical.source_name == "remotive_test"
    assert canonical.source_job_id == "123"
    assert canonical.title_raw == "Data Engineer"
    assert canonical.company_raw == "TechCo"
    assert canonical.work_arrangement == "remote"
    assert canonical.employment_type == "full_time"


def test_remotive_fetch_connect_error() -> None:
    config = SourceConfig(
        name="remotive_test",
        source_type=SourceType.aggregator_api,
        base_url="https://remotive.com/api/remote-jobs",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = RemotiveConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client)
        assert result.records_fetched == 0
        assert result.records_failed == 1
        assert len(result.errors) == 1
        assert result.errors[0].phase == "fetch"


# ---------------------------------------------------------------------------
# ArbeitnowConnector Tests
# ---------------------------------------------------------------------------


def test_arbeitnow_fetch_success() -> None:
    config = SourceConfig(
        name="arbeitnow_test",
        source_type=SourceType.aggregator_api,
        base_url="https://www.arbeitnow.com/api/job-board-api",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = ArbeitnowConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/job-board-api"
        payload = {
            "data": [
                {
                    "slug": "data-eng-123",
                    "title": "Data Engineer",
                    "company_name": "DataCo",
                    "url": "https://arbeitnow.com/jobs/data-eng-123",
                    "description": "ETL",
                    "location": "Berlin",
                    "remote": True,
                    "created_at": 1705312800,
                }
            ]
        }
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client, limit=10)
        assert result.source_name == "arbeitnow_test"
        assert result.records_fetched == 1
        assert len(result.records) == 1
        assert result.records_failed == 0
        assert len(result.errors) == 0


def test_arbeitnow_normalize() -> None:
    config = SourceConfig(
        name="arbeitnow_test",
        source_type=SourceType.aggregator_api,
        base_url="https://www.arbeitnow.com/api/job-board-api",
    )
    connector = ArbeitnowConnector(config)
    raw_record = RawJobRecord(
        source_name="arbeitnow_test",
        source_job_id="data-eng-123",
        content_hash="hash456",
        raw_payload='{"slug": "data-eng-123", "title": "Data Engineer", "company_name": "DataCo", "url": "https://arbeitnow.com/jobs/data-eng-123", "description": "ETL", "location": "Berlin", "remote": true, "created_at": 1705312800}',
        source_url="https://arbeitnow.com/jobs/data-eng-123",
    )
    canonical = connector.normalize(raw_record)
    assert canonical.job_id == "arbeitnow_data-eng-123"
    assert canonical.source_name == "arbeitnow_test"
    assert canonical.source_job_id == "data-eng-123"
    assert canonical.title_raw == "Data Engineer"
    assert canonical.company_raw == "DataCo"
    assert canonical.work_arrangement == "remote"


def test_arbeitnow_fetch_connect_error() -> None:
    config = SourceConfig(
        name="arbeitnow_test",
        source_type=SourceType.aggregator_api,
        base_url="https://www.arbeitnow.com/api/job-board-api",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = ArbeitnowConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client)
        assert result.records_fetched == 0
        assert result.records_failed == 1
        assert len(result.errors) == 1
        assert result.errors[0].phase == "fetch"


# ---------------------------------------------------------------------------
# GreenhouseConnector Tests
# ---------------------------------------------------------------------------


def test_greenhouse_fetch_success() -> None:
    config = SourceConfig(
        name="greenhouse_gitlab",
        source_type=SourceType.ats_greenhouse,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        board_identifier="gitlab",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = GreenhouseConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/boards/gitlab/jobs"
        payload = {
            "jobs": [
                {
                    "id": 456,
                    "title": "ML Engineer",
                    "absolute_url": "https://boards.greenhouse.io/gitlab/jobs/456",
                    "content": "Deep learning",
                    "location": {"name": "Remote"},
                    "updated_at": "2024-01-10T12:00:00",
                    "_board_identifier": "gitlab",
                }
            ]
        }
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client, limit=10)
        assert result.source_name == "greenhouse_gitlab"
        assert result.records_fetched == 1
        assert len(result.records) == 1
        assert result.records_failed == 0
        assert len(result.errors) == 0


def test_greenhouse_normalize() -> None:
    config = SourceConfig(
        name="greenhouse_gitlab",
        source_type=SourceType.ats_greenhouse,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        board_identifier="gitlab",
    )
    connector = GreenhouseConnector(config)
    raw_record = RawJobRecord(
        source_name="greenhouse_gitlab",
        source_job_id="gitlab_456",
        content_hash="hash789",
        raw_payload='{"id": 456, "title": "ML Engineer", "absolute_url": "https://boards.greenhouse.io/gitlab/jobs/456", "content": "Deep learning", "location": {"name": "Remote"}, "updated_at": "2024-01-10T12:00:00", "_board_identifier": "gitlab"}',
        source_url="https://boards.greenhouse.io/gitlab/jobs/456",
    )
    canonical = connector.normalize(raw_record)
    assert canonical.job_id == "greenhouse_gitlab_456"
    assert canonical.source_name == "greenhouse_gitlab"
    assert canonical.source_job_id == "gitlab_456"
    assert canonical.title_raw == "ML Engineer"
    assert canonical.company_raw == "Gitlab"
    assert canonical.work_arrangement == "remote"


def test_greenhouse_fetch_connect_error() -> None:
    config = SourceConfig(
        name="greenhouse_gitlab",
        source_type=SourceType.ats_greenhouse,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        board_identifier="gitlab",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = GreenhouseConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client)
        assert result.records_fetched == 0
        assert result.records_failed == 1
        assert len(result.errors) == 1
        assert result.errors[0].phase == "fetch"


# ---------------------------------------------------------------------------
# LeverConnector Tests
# ---------------------------------------------------------------------------


def test_lever_fetch_success() -> None:
    config = SourceConfig(
        name="lever_spotify",
        source_type=SourceType.ats_lever,
        base_url="https://api.lever.co/v0/postings",
        company_identifier="spotify",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = LeverConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v0/postings/spotify"
        payload = [
            {
                "id": "abc-123",
                "text": "Analytics Engineer",
                "hostedUrl": "https://jobs.lever.co/spotify/abc-123",
                "applyUrl": "https://jobs.lever.co/spotify/abc-123/apply",
                "descriptionPlain": "SQL expert",
                "categories": {"location": "Remote - US"},
                "createdAt": 1705312800000,
                "_company_identifier": "spotify",
            }
        ]
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client, limit=10)
        assert result.source_name == "lever_spotify"
        assert result.records_fetched == 1
        assert len(result.records) == 1
        assert result.records_failed == 0
        assert len(result.errors) == 0


def test_lever_normalize() -> None:
    config = SourceConfig(
        name="lever_spotify",
        source_type=SourceType.ats_lever,
        base_url="https://api.lever.co/v0/postings",
        company_identifier="spotify",
    )
    connector = LeverConnector(config)
    raw_record = RawJobRecord(
        source_name="lever_spotify",
        source_job_id="spotify_abc-123",
        content_hash="hashabc",
        raw_payload='{"id": "abc-123", "text": "Analytics Engineer", "hostedUrl": "https://jobs.lever.co/spotify/abc-123", "applyUrl": "https://jobs.lever.co/spotify/abc-123/apply", "descriptionPlain": "SQL expert", "categories": {"location": "Remote - US"}, "createdAt": 1705312800000, "_company_identifier": "spotify"}',
        source_url="https://jobs.lever.co/spotify/abc-123",
    )
    canonical = connector.normalize(raw_record)
    assert canonical.job_id == "lever_spotify_abc-123"
    assert canonical.source_name == "lever_spotify"
    assert canonical.source_job_id == "spotify_abc-123"
    assert canonical.title_raw == "Analytics Engineer"
    assert canonical.company_raw == "Spotify"
    assert canonical.work_arrangement == "remote"


def test_lever_fetch_connect_error() -> None:
    config = SourceConfig(
        name="lever_spotify",
        source_type=SourceType.ats_lever,
        base_url="https://api.lever.co/v0/postings",
        company_identifier="spotify",
        request_timeout=1.0,
        max_retries=1,
        rate_limit_delay=0.01,
    )
    connector = LeverConnector(config)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = connector.fetch(client)
        assert result.records_fetched == 0
        assert result.records_failed == 1
        assert len(result.errors) == 1
        assert result.errors[0].phase == "fetch"
