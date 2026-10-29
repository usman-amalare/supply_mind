"""Stock-adjustment request and response models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from supplymind.db.enums import StockReason

LedgerStatus = Literal["ok", "uninitialized", "mismatch"]

# Public adjustments never accept reason=initial. That path is product create / backfill.
AdjustmentReason = Literal[
    "receipt",
    "sale_deduction",
    "damage",
    "correction",
    "manual_count",
]


class StockAdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delta: Decimal = Field(max_digits=14, decimal_places=3)
    reason: AdjustmentReason
    note: str | None = Field(default=None, max_length=2000)
    source_ref: str | None = Field(default=None, max_length=200)


class StockAdjustmentView(BaseModel):
    id: UUID
    product_id: UUID
    delta: Decimal
    reason: StockReason
    note: str | None
    actor_user_id: UUID | None
    balance_after: Decimal
    source_ref: str | None
    created_at: datetime


class ProductStockSummary(BaseModel):
    product_id: UUID
    current_stock: Decimal
    ledger_status: LedgerStatus
    latest_balance_after: Decimal | None
