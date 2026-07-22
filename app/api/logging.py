"""Structured JSON logging and correlation context."""

from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime, timezone

correlation_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id",
    default="unbound",
)


class StructuredJSONFormatter(logging.Formatter):
    """Serialize operational records without request bodies or secrets."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_context.get(),
        }
        for name in (
            "event",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "session_id",
            "player_id",
            "exception_type",
        ):
            if hasattr(record, name):
                payload[name] = getattr(record, name)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_structured_logging(level: str) -> None:
    """Configure the application logger without logging configuration values."""

    logger = logging.getLogger("app.api")
    logger.setLevel(level)
    if not any(
        isinstance(handler.formatter, StructuredJSONFormatter)
        for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)
    logger.propagate = False
