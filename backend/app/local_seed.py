"""Local development only: create tables in DynamoDB Local and add sample events.

Run by the `seed` service in docker-compose.yml. In AWS, Terraform creates
the tables and organisers add events through POST /api/events.
"""

from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.models import EventCreate
from app.repository import EventAlreadyExists, Repository

SAMPLE_EVENTS = [
    EventCreate(
        event_id="aws-cloud-101",
        name="AWS Cloud 101 Workshop",
        venue="Seminar Hall A",
        starts_at=datetime.now(UTC) + timedelta(days=7),
        capacity=120,
    ),
    EventCreate(
        event_id="devops-bootcamp",
        name="Hands-on DevOps Bootcamp",
        venue="Lab 3",
        starts_at=datetime.now(UTC) + timedelta(days=14),
        capacity=3,
    ),
]


def main() -> None:
    repo = Repository(get_settings())
    repo.ensure_tables()
    for event in SAMPLE_EVENTS:
        try:
            repo.create_event(event)
            print(f"created {event.event_id}")
        except EventAlreadyExists:
            print(f"exists  {event.event_id}")


if __name__ == "__main__":
    main()
