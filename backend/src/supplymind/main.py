"""Application factory. Importing this module does not open a database connection."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from supplymind import __version__
from supplymind.api.router import api_router
from supplymind.clock import Clock, SystemClock
from supplymind.config import Settings, get_settings
from supplymind.core.errors import AppError, error_envelope
from supplymind.core.logging import configure_logging, request_id_var
from supplymind.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from supplymind.core.rate_limit import InMemoryRateLimiter
from supplymind.db.session import make_engine

_logger = logging.getLogger("supplymind.errors")

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return request_id_var.get()


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved.log_level)
    docs_url = "/docs" if resolved.app_env != "production" else None
    openapi_url = "/openapi.json" if resolved.app_env != "production" else None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(app.state.settings.database_url)
        app.state.engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="SupplyMind",
        version=__version__,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.clock = clock or SystemClock()
    app.state.rate_limiter = InMemoryRateLimiter(app.state.clock)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(request: Request) -> JSONResponse:
        engine = request.app.state.engine
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            _logger.error("readiness check failed: %s", type(exc).__name__)
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(status_code=200, content={"status": "ok"})

    app.include_router(api_router, prefix="/api/v1")

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.code, exc.message, _request_id(request), exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "loc": [str(part) for part in item.get("loc", ())],
                "msg": str(item.get("msg", "")),
                "type": str(item.get("type", "")),
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "validation_error",
                "Request validation failed",
                _request_id(request),
                details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        if exc.status_code >= 500 or not isinstance(exc.detail, str):
            message = "Internal server error" if exc.status_code >= 500 else "Request failed"
        else:
            message = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(code, message, _request_id(request)),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        token = request_id_var.set(request_id)
        try:
            _logger.exception("unhandled error type=%s", type(exc).__name__)
        finally:
            request_id_var.reset(token)
        return JSONResponse(
            status_code=500,
            content=error_envelope("internal_error", "Internal server error", request_id),
        )

    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=resolved.app_env == "production")
    app.add_middleware(RequestIdMiddleware)
    origins = resolved.frontend_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", resolved.csrf_header_name, "X-Request-ID"],
            expose_headers=["X-Request-ID"],
            max_age=600,
        )
    return app
