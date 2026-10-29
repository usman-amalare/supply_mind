"""Catalog tables. SKU uniqueness is case-insensitive inside a workspace."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import VendorRole, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin


class Vendor(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_vendors_workspace_id"),
        CheckConstraint("char_length(btrim(name)) > 0", name="name_present"),
        CheckConstraint("typical_lead_time_days >= 0", name="lead_time_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    typical_lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    imports_goods: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_products_workspace_id"),
        CheckConstraint("char_length(btrim(sku)) > 0", name="sku_present"),
        CheckConstraint("char_length(btrim(name)) > 0", name="name_present"),
        CheckConstraint("reorder_threshold >= 0", name="reorder_threshold_non_negative"),
        CheckConstraint("current_stock >= 0", name="current_stock_non_negative"),
        CheckConstraint(
            "(unit_cost IS NULL AND unit_cost_currency IS NULL) OR "
            "(unit_cost IS NOT NULL AND unit_cost >= 0 AND unit_cost_currency ~ '^[A-Z]{3}$')",
            name="unit_cost_with_currency",
        ),
    )

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    reorder_threshold: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    unit_cost_currency: Mapped[str | None] = mapped_column(String(3))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "uq_products_workspace_lower_sku",
    Product.workspace_id,
    func.lower(Product.sku),
    unique=True,
)


class ProductVendor(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "product_vendors"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_product_vendors_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "product_id",
            "vendor_id",
            name="uq_product_vendors_product_vendor",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_product_vendors_product",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "vendor_id"],
            ["vendors.workspace_id", "vendors.id"],
            name="fk_product_vendors_vendor",
        ),
    )

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    vendor_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    role: Mapped[VendorRole] = mapped_column(
        pg_enum(VendorRole, "ck_product_vendors_role"),
        nullable=False,
    )


Index(
    "uq_product_vendors_one_primary",
    ProductVendor.workspace_id,
    ProductVendor.product_id,
    unique=True,
    postgresql_where=text("role = 'primary'"),
)
Index(
    "uq_product_vendors_one_backup",
    ProductVendor.workspace_id,
    ProductVendor.product_id,
    unique=True,
    postgresql_where=text("role = 'backup'"),
)
