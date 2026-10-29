"""Orders and lines. Delivered orders must carry an actual delivery date."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import OrderStatus, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin


class Order(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_orders_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "vendor_id"],
            ["vendors.workspace_id", "vendors.id"],
            name="fk_orders_vendor",
        ),
        CheckConstraint(
            "(status = 'delivered') = (actual_delivery_date IS NOT NULL)",
            name="delivered_has_date",
        ),
    )

    vendor_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_delivery_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "ck_orders_status"),
        nullable=False,
    )


class OrderLine(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_order_lines_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "order_id"],
            ["orders.workspace_id", "orders.id"],
            name="fk_order_lines_order",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_order_lines_product",
        ),
        CheckConstraint("qty_ordered > 0", name="qty_ordered_positive"),
        CheckConstraint("qty_received >= 0", name="qty_received_non_negative"),
    )

    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
