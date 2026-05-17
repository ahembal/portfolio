"""
HTTP request logging middleware for p2 metadata ingestion service.

Logs one structured JSON line per request containing:
  request_id, http.method, url.path, http.status_code, duration_ms

The request_id is read from the X-Request-ID header if present,
otherwise generated. It is added to the response headers so callers
can correlate logs with their own request tracking.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = logging.getLogger("p2-metadata-ingestion.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        t0 = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - t0) * 1000, 1)

        log.info(
            "request_completed",
            extra={
                "request_id":       request_id,
                "http.method":      request.method,
                "url.path":         request.url.path,
                "http.status_code": response.status_code,
                "duration_ms":      duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
