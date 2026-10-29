"""Request id and security headers."""

from __future__ import annotations

import logging
import re

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from supplymind.core.ids import new_id
from supplymind.core.logging import request_id_var

_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_logger = logging.getLogger("supplymind.access")
_CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.fullmatch(incoming) else str(new_id())
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["request_id"] = request_id
        token = request_id_var.set(request_id)
        status_code = 0

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            if status_code == 0:
                status_code = 500
            raise
        finally:
            method = str(scope.get("method", "-"))
            path = str(scope.get("path", "-"))
            _logger.info("%s %s %s", method, path, status_code)
            request_id_var.reset(token)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, enable_hsts: bool) -> None:
        self.app = app
        self.enable_hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
                if self.enable_hsts:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_with_headers)
