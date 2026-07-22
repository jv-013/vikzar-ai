"""Correlation, authentication, body-limit, logging, and metrics middleware."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .auth import Authenticator
from .contracts import APIErrorDetail, APIErrorResponse
from .logging import correlation_id_context
from .metrics import MetricsRegistry

_CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PUBLIC_PATHS = frozenset({"/health/live", "/health/ready"})


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    clock: Callable[[], datetime],
    details: tuple[str, ...] = (),
) -> JSONResponse:
    payload = APIErrorResponse(
        error=APIErrorDetail(
            code=code,
            message=message,
            correlation_id=correlation_id,
            timestamp=clock(),
            details=details,
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Validate or create one trace identity and echo it on every response."""

    def __init__(self, app, *, clock: Callable[[], datetime]) -> None:
        super().__init__(app)
        self._clock = clock

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        if not _CORRELATION_PATTERN.fullmatch(correlation_id):
            return error_response(
                status_code=400,
                code="API_INVALID_CORRELATION_ID",
                message="Correlation ID is invalid.",
                correlation_id="rejected",
                clock=self._clock,
            )
        request.state.correlation_id = correlation_id
        token = correlation_id_context.set(correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            correlation_id_context.reset(token)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Invoke the injected provider without implementing an auth scheme."""

    def __init__(
        self,
        app,
        *,
        authenticator: Authenticator,
        auth_required: bool,
        clock: Callable[[], datetime],
    ) -> None:
        super().__init__(app)
        self._authenticator = authenticator
        self._required = auth_required
        self._clock = clock

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        token = ""
        if header:
            scheme, _, token = header.partition(" ")
            if scheme.lower() != "bearer" or not token:
                return self._unauthorized(request)
        if self._required and not token:
            return self._unauthorized(request)
        try:
            request.state.principal = await self._authenticator.authenticate(token)
        except Exception:
            return self._unauthorized(request)
        return await call_next(request)

    def _unauthorized(self, request: Request) -> JSONResponse:
        return error_response(
            status_code=401,
            code="API_UNAUTHORIZED",
            message="Authentication failed.",
            correlation_id=getattr(request.state, "correlation_id", "unbound"),
            clock=self._clock,
        )


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject declared request bodies beyond the configured local limit."""

    def __init__(
        self,
        app,
        *,
        max_bytes: int,
        clock: Callable[[], datetime],
    ) -> None:
        super().__init__(app)
        self._max = max_bytes
        self._clock = clock

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                too_large = int(content_length) > self._max
            except ValueError:
                too_large = True
            if too_large:
                return error_response(
                    status_code=413,
                    code="API_REQUEST_TOO_LARGE",
                    message="Request body exceeds the configured limit.",
                    correlation_id=getattr(
                        request.state,
                        "correlation_id",
                        "unbound",
                    ),
                    clock=self._clock,
                )
        body = await request.body()
        if len(body) > self._max:
            return error_response(
                status_code=413,
                code="API_REQUEST_TOO_LARGE",
                message="Request body exceeds the configured limit.",
                correlation_id=getattr(
                    request.state,
                    "correlation_id",
                    "unbound",
                ),
                clock=self._clock,
            )
        return await call_next(request)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Log request metadata and record counters without logging bodies."""

    def __init__(self, app, *, metrics: MetricsRegistry) -> None:
        super().__init__(app)
        self._metrics = metrics
        self._logger = logging.getLogger("app.api")

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        failed = response.status_code >= 400
        self._metrics.record_request(failed=failed)
        self._logger.info(
            "request.completed",
            extra={
                "event": "request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
