"""Structured (JSON) logging.

Every log line is one JSON object written to stdout. Lambda forwards stdout
to CloudWatch Logs automatically, and JSON lets CloudWatch Logs Insights
query fields directly, e.g.

    fields @timestamp, path, status, duration_ms
    | filter status >= 500
    | sort @timestamp desc
"""

import json
import logging
import sys
from datetime import UTC, datetime

# Extra fields we allow callers to attach with logger.info("...", extra={...}).
_EXTRA_FIELDS = (
    "request_id",
    "method",
    "path",
    "status",
    "duration_ms",
    "event_id",
    "registration_id",
    "error",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Lambda pre-installs its own handler; replace it so we don't log twice.
    root.handlers = [handler]
    root.setLevel(level)
