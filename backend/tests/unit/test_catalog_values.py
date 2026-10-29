from __future__ import annotations

from decimal import Decimal

import pytest

from supplymind.modules.catalog.values import money, optional_text, quantity, required_text


def test_required_text_strips_and_rejects_blank() -> None:
    assert required_text("  bag  ", 32) == "bag"
    with pytest.raises(ValueError, match="invalid text"):
        required_text("   ", 32)


def test_optional_text_turns_blank_into_none() -> None:
    assert optional_text("  ", 40) is None
    assert optional_text("Ada", 40) == "Ada"


def test_quantity_and_money_bounds() -> None:
    assert quantity(Decimal("1.500")) == Decimal("1.500")
    with pytest.raises(ValueError):
        quantity(Decimal("-0.001"))
    with pytest.raises(ValueError):
        money(Decimal("1.001"))
