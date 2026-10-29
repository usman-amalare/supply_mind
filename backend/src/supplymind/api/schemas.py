"""Shared API models. SQLAlchemy rows are not response models."""

from __future__ import annotations

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    loc: list[str]
    msg: str
    type: str


class ErrorBodyModel(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[ValidationIssue] | dict[str, str] | None = None


class ErrorEnvelopeModel(BaseModel):
    error: ErrorBodyModel


def error_responses(*codes: int) -> dict[int | str, dict[str, type[ErrorEnvelopeModel]]]:
    return {code: {"model": ErrorEnvelopeModel} for code in codes}
