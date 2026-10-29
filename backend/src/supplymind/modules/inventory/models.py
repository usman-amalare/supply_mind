"""Append-only stock adjustments. UPDATE and DELETE are rejected by a database trigger."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import StockReason, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin


class StockAdjustment(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "stock_adjustments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_stock_adjustments_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_stock_adjustments_product",
        ),
        CheckConstraint("char_length(reason) > 0", name="reason_present"),
    )

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[StockReason] = mapped_column(
        pg_enum(StockReason, "ck_stock_adjustments_reason"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(200))


Index(
    "ix_stock_adjustments_product_created",
    StockAdjustment.workspace_id,
    StockAdjustment.product_id,
    StockAdjustment.created_at,
)
