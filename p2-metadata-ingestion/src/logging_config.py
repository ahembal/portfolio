"""
Structured JSON logging setup for p2 metadata ingestion service.

Emits OTel-compatible JSON log lines to stdout. Each line contains:
  timestamp, level, logger, message, service.name, environment,
  request_id (when available), and domain-specific fields.

Usage:
  from src.logging_config import setup_logging
  log = setup_logging()
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formats log records as a single JSON line per event."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%S.") +
                         f"{record.created % 1 * 1000:03.0f}Z",
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.getMessage(),
            "service.name": os.getenv("SERVICE_NAME", "p2-metadata-ingestion"),
            "environment":  os.getenv("ENVIRONMENT", "production"),
        }

        # Merge any extra fields passed via log.info("msg", extra={...})
        for key, val in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "taskName",
            ):
                log_entry[key] = val

        if record.exc_info:
            log_entry["exception_type"]    = record.exc_info[0].__name__
            log_entry["exception_message"] = str(record.exc_info[1])

        return json.dumps(log_entry)


def setup_logging(name: str = "p2-metadata-ingestion") -> logging.Logger:
    """
    Configure root logger to emit JSON and return a named logger.

    Call once at application startup.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger(name)
