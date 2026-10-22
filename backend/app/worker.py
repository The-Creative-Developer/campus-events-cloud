"""SQS-triggered Lambda that sends registration confirmation emails.

Same container image as the API, different entry point (`app.worker.handler`).

Failure handling: Lambda receives up to 10 messages per batch. If one email
fails we report just that message in `batchItemFailures`; SQS retries only
that one instead of the whole batch (no duplicate emails for the other 9).
After 5 failed attempts SQS moves the message to the dead-letter queue,
where a CloudWatch alarm notices it.
"""

import logging
from functools import lru_cache

import boto3

from app.config import get_settings
from app.logging_config import configure_logging
from app.notifications import parse_message

configure_logging()
logger = logging.getLogger("campus_events.worker")


@lru_cache
def ses_client():
    return boto3.client("ses", region_name=get_settings().aws_region)


def send_confirmation(body: str) -> None:
    registration = parse_message(body)
    sender = get_settings().sender_email
    if not sender:
        logger.info("SENDER_EMAIL not set, not sending", extra={"registration_id": registration.registration_id})
        return
    ses_client().send_email(
        Source=sender,
        Destination={"ToAddresses": [registration.email]},
        Message={
            "Subject": {"Data": f"You're registered: {registration.event_id}"},
            "Body": {
                "Text": {
                    "Data": (
                        f"Hi {registration.name},\n\n"
                        f"Your seat for {registration.event_id} is confirmed.\n"
                        f"Registration ID: {registration.registration_id}\n"
                    )
                }
            },
        },
    )
    logger.info("confirmation sent", extra={"registration_id": registration.registration_id})


def handler(event, context):
    failures = []
    for record in event.get("Records", []):
        try:
            send_confirmation(record["body"])
        except Exception as err:
            logger.exception("Failed to send confirmation", extra={"error": str(err)})
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
