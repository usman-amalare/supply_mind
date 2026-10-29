"""Catalog field checks. Messages do not echo the submitted value."""

from __future__ import annotations

from decimal import Decimal

_MAX_QUANTITY = Decimal("99999999999.999")
_MAX_MONEY = Decimal("999999999999.99")


def required_text(value: str, limit: int) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        raise ValueError("invalid text")
    return cleaned


def optional_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > limit:
        raise ValueError("invalid text")
    return cleaned


def quantity(value: Decimal) -> Decimal:
    return _decimal(value, places=3, upper=_MAX_QUANTITY)


def money(value: Decimal) -> Decimal:
    return _decimal(value, places=2, upper=_MAX_MONEY)


def _decimal(value: Decimal, *, places: int, upper: Decimal) -> Decimal:
    if not value.is_finite() or value < 0 or value > upper:
        raise ValueError("invalid amount")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -places:
        raise ValueError("invalid amount")
    return value
