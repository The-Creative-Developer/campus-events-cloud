"""Tests for the two Lambda entry points (API handler and email worker)."""

import json
from pathlib import Path

import boto3

from app import main, worker

HEALTH_EVENT = Path(__file__).parents[2] / "scripts" / "health-event.json"


def test_api_gateway_event_reaches_fastapi(client):
    """The same JSON event the deploy pipeline uses to smoke-test a new version."""
    event = json.loads(HEALTH_EVENT.read_text())
    resp = main.handler(event, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["status"] == "ok"


def _record(message_id, body):
    return {"messageId": message_id, "body": body}


def test_worker_sends_email_and_reports_only_bad_messages(aws, monkeypatch):
    monkeypatch.setenv("SENDER_EMAIL", "events@example.edu")
    ses = boto3.client("ses", region_name="ap-south-1")
    ses.verify_email_identity(EmailAddress="events@example.edu")
    worker.ses_client.cache_clear()

    good = json.dumps({"registration_id": "r-1", "event_id": "cloud-101", "name": "Asha", "email": "asha@example.edu"})
    result = worker.handler({"Records": [_record("m1", good), _record("m2", "not json")]}, None)

    assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}
    assert ses.get_send_quota()["SentLast24Hours"] == 1
