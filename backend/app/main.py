"""HTTP API for campus event registration.

Runs two ways from the same code:
  * locally:   uvicorn app.main:app          (a normal web server)
  * on AWS:    Lambda handler `app.main.handler`
Mangum is a small adapter that turns an API Gateway event into a normal
HTTP request for FastAPI, and the response back into what API Gateway expects.
"""

import logging
import time
import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from mangum import Mangum

from app.config import Settings, get_settings
from app.logging_config import configure_logging
from app.models import Event, EventCreate, Registration, RegistrationRequest
from app.notifications import Notifier
from app.repository import AlreadyRegistered, EventAlreadyExists, EventFull, EventNotFound, Repository

configure_logging()
logger = logging.getLogger("campus_events.api")


# Objects created here survive between Lambda invocations while the
# execution environment stays "warm", so we build boto3 clients once instead
# of on every request (creating clients is slow).
@lru_cache
def settings_dep() -> Settings:
    return get_settings()


@lru_cache
def repository_dep() -> Repository:
    return Repository(settings_dep())


@lru_cache
def notifier_dep() -> Notifier:
    return Notifier(settings_dep())


def require_organiser(request: Request, settings: Settings = Depends(settings_dep)) -> None:
    """Defence in depth for admin routes.

    API Gateway already rejects requests without a valid Cognito JWT before
    Lambda is invoked. We additionally check the caller is in the
    'organisers' group, so a misconfigured route can't silently become public.
    """
    if settings.admin_auth_disabled:
        return
    aws_event = request.scope.get("aws.event") or {}
    claims = aws_event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    if "organisers" not in str(claims.get("cognito:groups", "")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organiser access required")


app = FastAPI(title="Campus Events API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
router = APIRouter(prefix="/api")


@app.middleware("http")
async def access_log(request: Request, call_next):
    """One structured log line per request, tagged with a request id.

    On Lambda we reuse the AWS request id so a log line can be matched to the
    Lambda invocation and X-Ray trace. The id is also returned to the client
    in X-Request-Id, so a student reporting a problem can quote it.
    """
    aws_context = request.scope.get("aws.context")
    request_id = getattr(aws_context, "aws_request_id", None) or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error", extra={"request_id": request_id, "path": request.url.path})
        raise
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response


@router.get("/health")
def health(settings: Settings = Depends(settings_dep)) -> dict:
    """Liveness: the code is running. Used by the deploy smoke test."""
    return {"status": "ok", "version": settings.app_version}


@router.get("/health/ready")
def ready(repo: Repository = Depends(repository_dep)) -> dict:
    """Readiness: we can actually reach the database."""
    try:
        repo.client.describe_table(TableName=repo.events_table)
    except Exception as err:
        logger.exception("Readiness check failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unreachable") from err
    return {"status": "ready"}


@router.get("/events")
def list_events(repo: Repository = Depends(repository_dep)) -> list[Event]:
    return repo.list_events()


@router.get("/events/{event_id}")
def get_event(event_id: str, repo: Repository = Depends(repository_dep)) -> Event:
    try:
        return repo.get_event(event_id)
    except EventNotFound as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found") from err


@router.post("/events", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_organiser)])
def create_event(body: EventCreate, repo: Repository = Depends(repository_dep)) -> Event:
    try:
        return repo.create_event(body)
    except EventAlreadyExists as err:
        raise HTTPException(status.HTTP_409_CONFLICT, "An event with this id already exists") from err


@router.post("/events/{event_id}/registrations", status_code=status.HTTP_201_CREATED)
def register(
    event_id: str,
    body: RegistrationRequest,
    repo: Repository = Depends(repository_dep),
    notifier: Notifier = Depends(notifier_dep),
) -> Registration:
    try:
        registration = repo.register(event_id, body)
    except EventNotFound as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found") from err
    except AlreadyRegistered as err:
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered for the event") from err
    except EventFull as err:
        raise HTTPException(status.HTTP_409_CONFLICT, "Sorry, this event is full") from err
    logger.info(
        "registration confirmed",
        extra={"event_id": event_id, "registration_id": registration.registration_id},
    )
    notifier.registration_confirmed(registration)
    return registration


app.include_router(router)

# Lambda entry point. lifespan="off" because Lambda has no server start/stop.
handler = Mangum(app, lifespan="off")
