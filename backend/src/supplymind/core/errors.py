"""Application errors and the single HTTP error envelope."""

from __future__ import annotations

from typing import TypedDict


class ErrorBody(TypedDict, total=False):
    code: str
    message: str
    details: object
    request_id: str


class ErrorEnvelope(TypedDict):
    error: ErrorBody


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_envelope(
    code: str,
    message: str,
    request_id: str,
    details: object | None = None,
) -> ErrorEnvelope:
    body: ErrorBody = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        body["details"] = details
    return {"error": body}
