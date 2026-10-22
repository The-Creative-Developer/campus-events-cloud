"""Hands confirmation emails off to a queue instead of sending them inline.

Why a queue? Sending email is slow and can fail (rate limits, SES outages).
If the API sent emails itself, a slow email provider would make every
registration slow during peak traffic. Putting a message on SQS takes a few
milliseconds; a separate worker Lambda sends the emails at its own pace and
retries on failure. Messages that keep failing land in a dead-letter queue.
"""

import json
import logging

import boto3

from app.config import Settings
from app.models import Registration

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, settings: Settings, client=None):
        self.queue_url = settings.queue_url
        self.client = client or (boto3.client("sqs", region_name=settings.aws_region) if self.queue_url else None)

    def registration_confirmed(self, registration: Registration) -> None:
        if not self.queue_url:
            logger.info("No queue configured, skipping confirmation email", extra={"event_id": registration.event_id})
            return
        try:
            self.client.send_message(QueueUrl=self.queue_url, MessageBody=registration.model_dump_json())
        except Exception:
            # The seat is already saved in DynamoDB. Failing the whole request
            # now would tell the student "error" for a registration that
            # actually succeeded, so we log loudly (an alarm watches for this)
            # and still return success.
            logger.exception(
                "Failed to enqueue confirmation email",
                extra={"registration_id": registration.registration_id},
            )


def parse_message(body: str) -> Registration:
    return Registration(**json.loads(body))
