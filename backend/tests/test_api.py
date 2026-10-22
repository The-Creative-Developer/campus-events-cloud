import json

import boto3
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import main

STUDENT = {"name": "Asha Patil", "email": "asha@example.edu", "student_id": "VIT2026001"}


def test_health_reports_running_version(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "test-sha"}
    assert resp.headers["X-Request-Id"]


def test_ready_checks_database(client):
    assert client.get("/api/health/ready").json() == {"status": "ready"}


def test_list_events_shows_seats_left(client, make_event):
    make_event(capacity=50)
    events = client.get("/api/events").json()
    assert [(e["event_id"], e["seats_left"]) for e in events] == [("cloud-101", 50)]


def test_unknown_event_is_404(client):
    assert client.get("/api/events/nope").status_code == 404


def test_register_takes_a_seat_and_queues_email(client, make_event, queue_url):
    make_event(capacity=2)

    resp = client.post("/api/events/cloud-101/registrations", json=STUDENT)

    assert resp.status_code == 201
    assert resp.json()["status"] == "confirmed"
    assert client.get("/api/events/cloud-101").json()["seats_left"] == 1
    messages = boto3.client("sqs", region_name="ap-south-1").receive_message(QueueUrl=queue_url)["Messages"]
    assert json.loads(messages[0]["Body"])["email"] == "asha@example.edu"


def test_same_email_cannot_register_twice(client, make_event):
    make_event(capacity=5)
    client.post("/api/events/cloud-101/registrations", json=STUDENT)

    # Different capitalisation is still the same person.
    again = client.post("/api/events/cloud-101/registrations", json=STUDENT | {"email": "ASHA@example.edu"})

    assert again.status_code == 409
    assert "already registered" in again.json()["detail"]
    assert client.get("/api/events/cloud-101").json()["seats_left"] == 4


def test_full_event_rejects_and_never_overbooks(client, make_event):
    make_event(capacity=2)
    codes = [
        client.post(
            "/api/events/cloud-101/registrations",
            json=STUDENT | {"email": f"student{i}@example.edu"},
        ).status_code
        for i in range(4)
    ]
    assert codes == [201, 201, 409, 409]
    event = client.get("/api/events/cloud-101").json()
    assert event["registered_count"] == 2
    assert event["seats_left"] == 0


def test_register_for_missing_event_is_404(client):
    assert client.post("/api/events/ghost/registrations", json=STUDENT).status_code == 404


@pytest.mark.parametrize(
    "bad",
    [{"email": "not-an-email"}, {"student_id": "x"}, {"name": ""}],
)
def test_invalid_input_is_rejected_before_database(client, make_event, bad):
    make_event()
    assert client.post("/api/events/cloud-101/registrations", json=STUDENT | bad).status_code == 422


def test_create_event_requires_organiser(client):
    resp = client.post(
        "/api/events",
        json={"event_id": "hack-1", "name": "Hack", "venue": "Lab", "starts_at": "2026-11-01T10:00:00Z", "capacity": 5},
    )
    assert resp.status_code == 403


def _request_with_groups(groups: str) -> Request:
    claims = {"cognito:groups": groups} if groups else {}
    event = {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}
    return Request({"type": "http", "aws.event": event})


def test_organiser_group_is_allowed():
    main.require_organiser(_request_with_groups("[organisers]"), main.get_settings())


def test_non_organiser_is_forbidden():
    with pytest.raises(HTTPException) as exc:
        main.require_organiser(_request_with_groups("[students]"), main.get_settings())
    assert exc.value.status_code == 403


def test_duplicate_event_id_is_409(client, make_event):
    make_event()
    main.app.dependency_overrides[main.require_organiser] = lambda: None
    resp = client.post(
        "/api/events",
        json={
            "event_id": "cloud-101",
            "name": "Dup",
            "venue": "Lab",
            "starts_at": "2026-11-01T10:00:00Z",
            "capacity": 5,
        },
    )
    assert resp.status_code == 409
