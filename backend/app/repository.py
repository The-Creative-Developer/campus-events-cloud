"""All DynamoDB access lives here.

Two tables:
  events         PK: event_id
  registrations  PK: event_id, SK: email   (one registration per email per event)

The interesting part is `register()`: at peak traffic hundreds of students
may try to grab the last few seats at the same moment. A naive
"read count -> check -> write" would let two requests both see "1 seat left"
and overbook. Instead we use a single DynamoDB transaction that
  1. increments registered_count ONLY IF registered_count < capacity, and
  2. inserts the registration ONLY IF this email hasn't registered yet.
Both succeed or neither does, so the seat count can never go over capacity
and a double-click can never create two registrations.
"""

import uuid
from datetime import UTC, datetime

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from app.config import Settings
from app.models import Event, EventCreate, Registration, RegistrationRequest

_serializer = TypeSerializer()
_deserializer = TypeDeserializer()


class EventNotFound(Exception):
    pass


class EventAlreadyExists(Exception):
    pass


class EventFull(Exception):
    pass


class AlreadyRegistered(Exception):
    pass


def _to_item(data: dict) -> dict:
    return {k: _serializer.serialize(v) for k, v in data.items()}


def _from_item(item: dict) -> dict:
    data = {k: _deserializer.deserialize(v) for k, v in item.items()}
    # DynamoDB returns numbers as Decimal; our counts are always whole numbers.
    return {k: int(v) if k in ("capacity", "registered_count") else v for k, v in data.items()}


def _to_event(item: dict) -> Event:
    data = _from_item(item)
    return Event(**data, seats_left=data["capacity"] - data["registered_count"])


class Repository:
    def __init__(self, settings: Settings, client=None):
        self.events_table = settings.events_table
        self.registrations_table = settings.registrations_table
        self.client = client or boto3.client(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint,
        )

    def list_events(self) -> list[Event]:
        # A Scan reads the whole table. That is fine for a club with tens of
        # events; with thousands we would Query a GSI (e.g. by date) instead.
        items, kwargs = [], {"TableName": self.events_table}
        while True:
            page = self.client.scan(**kwargs)
            items.extend(page["Items"])
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        events = [_to_event(item) for item in items]
        return sorted(events, key=lambda e: e.starts_at)

    def get_event(self, event_id: str) -> Event:
        resp = self.client.get_item(TableName=self.events_table, Key=_to_item({"event_id": event_id}))
        if "Item" not in resp:
            raise EventNotFound(event_id)
        return _to_event(resp["Item"])

    def create_event(self, event: EventCreate) -> Event:
        data = event.model_dump()
        data["starts_at"] = event.starts_at.isoformat()
        data["registered_count"] = 0
        try:
            self.client.put_item(
                TableName=self.events_table,
                Item=_to_item(data),
                ConditionExpression="attribute_not_exists(event_id)",
            )
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise EventAlreadyExists(event.event_id) from err
            raise
        return Event(**event.model_dump(), registered_count=0, seats_left=event.capacity)

    def register(self, event_id: str, req: RegistrationRequest) -> Registration:
        email = req.email.lower()
        registration = Registration(
            registration_id=str(uuid.uuid4()),
            event_id=event_id,
            name=req.name,
            email=email,
        )
        item = registration.model_dump() | {
            "student_id": req.student_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        try:
            self.client.transact_write_items(
                TransactItems=[
                    {
                        "Update": {
                            "TableName": self.events_table,
                            "Key": _to_item({"event_id": event_id}),
                            "UpdateExpression": "SET registered_count = registered_count + :one",
                            # "capacity" is a DynamoDB reserved word, so it must be
                            # referenced through a placeholder (#capacity).
                            "ConditionExpression": "attribute_exists(event_id) AND registered_count < #capacity",
                            "ExpressionAttributeNames": {"#capacity": "capacity"},
                            "ExpressionAttributeValues": {":one": {"N": "1"}},
                        }
                    },
                    {
                        "Put": {
                            "TableName": self.registrations_table,
                            "Item": _to_item(item),
                            "ConditionExpression": "attribute_not_exists(email)",
                        }
                    },
                ]
            )
        except ClientError as err:
            if err.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            reasons = [r.get("Code") for r in err.response.get("CancellationReasons", [])]
            if len(reasons) > 1 and reasons[1] == "ConditionalCheckFailed":
                raise AlreadyRegistered(email) from err
            # The seat update failed: either the event doesn't exist or it is full.
            self.get_event(event_id)  # raises EventNotFound if missing
            raise EventFull(event_id) from err
        return registration

    def ensure_tables(self) -> None:
        """Create the tables if missing. Used only for local development;
        in AWS the tables are created by Terraform."""
        existing = self.client.list_tables()["TableNames"]
        specs = {
            self.events_table: [("event_id", "HASH")],
            self.registrations_table: [("event_id", "HASH"), ("email", "RANGE")],
        }
        for name, keys in specs.items():
            if name in existing:
                continue
            self.client.create_table(
                TableName=name,
                BillingMode="PAY_PER_REQUEST",
                KeySchema=[{"AttributeName": k, "KeyType": t} for k, t in keys],
                AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k, _ in keys],
            )
            self.client.get_waiter("table_exists").wait(TableName=name)
