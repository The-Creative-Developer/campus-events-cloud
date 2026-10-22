"""Test fixtures.

`moto` fakes AWS in memory, so tests run in seconds, need no AWS account,
cost nothing and can't touch real data. Every test gets fresh, empty tables.
"""

import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

# Fake credentials so boto3 can never reach a real AWS account from tests.
os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "ap-south-1",
        "AWS_REGION": "ap-south-1",
        "APP_VERSION": "test-sha",
    }
)
os.environ.pop("DYNAMODB_ENDPOINT", None)

from app import main  # noqa: E402  (must import after setting env vars)
from app.config import get_settings  # noqa: E402
from app.notifications import Notifier  # noqa: E402
from app.repository import Repository  # noqa: E402


@pytest.fixture
def aws():
    with mock_aws():
        yield


@pytest.fixture
def queue_url(aws):
    sqs = boto3.client("sqs", region_name="ap-south-1")
    return sqs.create_queue(QueueName="confirmations")["QueueUrl"]


@pytest.fixture
def repo(aws):
    repository = Repository(get_settings())
    repository.ensure_tables()
    return repository


@pytest.fixture
def client(repo, queue_url, monkeypatch):
    monkeypatch.setenv("QUEUE_URL", queue_url)
    for cached in (main.settings_dep, main.repository_dep, main.notifier_dep):
        cached.cache_clear()
    main.app.dependency_overrides[main.repository_dep] = lambda: repo
    main.app.dependency_overrides[main.notifier_dep] = lambda: Notifier(get_settings())
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def make_event(client, monkeypatch):
    """Create an event through the API, as an organiser would."""

    def _make(event_id="cloud-101", capacity=2):
        main.app.dependency_overrides[main.require_organiser] = lambda: None
        resp = client.post(
            "/api/events",
            json={
                "event_id": event_id,
                "name": "Cloud 101",
                "venue": "Hall A",
                "starts_at": "2026-11-20T10:00:00Z",
                "capacity": capacity,
            },
        )
        del main.app.dependency_overrides[main.require_organiser]
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make
