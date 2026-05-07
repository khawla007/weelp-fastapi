import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from gateway.observability.logging import logger

REQUEST_ID_HEADER = "X-Request-Id"
# Trust an inbound id only if it looks sane. Untrusted clients should not be able
# to inject log-poisoning payloads or impersonate another caller's trace.
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER)
        request_id = inbound if inbound and _REQUEST_ID_PATTERN.match(inbound) else uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.exception(
                "request.error",
                method=request.method,
                path=request.url.path,
                latency_ms=latency_ms,
            )
            structlog.contextvars.clear_contextvars()
            raise

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request.complete",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        structlog.contextvars.clear_contextvars()
        return response
