"""Runtime configuration, read from environment variables.

The same container image runs locally (docker compose) and in AWS Lambda.
Only the environment variables change between the two - nothing is baked
into the image. This is the "config in the environment" rule from the
Twelve-Factor App.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    events_table: str
    registrations_table: str
    aws_region: str
    # Set only for local development (DynamoDB Local). Empty in AWS.
    dynamodb_endpoint: str | None
    # SQS queue for confirmation emails. Empty locally -> emails are skipped.
    queue_url: str | None
    # Git commit SHA of the running build, shown by /api/health.
    app_version: str
    # Sender address for confirmation emails (worker only).
    sender_email: str | None
    # Local development only: skip the organiser check on admin routes,
    # because there is no Cognito running on a laptop. Never set in AWS.
    admin_auth_disabled: bool


def get_settings() -> Settings:
    return Settings(
        events_table=os.environ.get("EVENTS_TABLE", "campus-events-events"),
        registrations_table=os.environ.get("REGISTRATIONS_TABLE", "campus-events-registrations"),
        aws_region=os.environ.get("AWS_REGION", "ap-south-1"),
        dynamodb_endpoint=os.environ.get("DYNAMODB_ENDPOINT") or None,
        queue_url=os.environ.get("QUEUE_URL") or None,
        app_version=os.environ.get("APP_VERSION", "dev"),
        sender_email=os.environ.get("SENDER_EMAIL") or None,
        admin_auth_disabled=os.environ.get("ADMIN_AUTH_DISABLED", "false").lower() == "true",
    )
