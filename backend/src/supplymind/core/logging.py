"""JSON logs. Query strings are not logged. Responses never include tracebacks."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers = [handler]
