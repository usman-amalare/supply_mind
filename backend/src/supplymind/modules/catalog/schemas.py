"""Catalog request and response models. Extra write fields are rejected."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from supplymind.db.enums import VendorRole


class VendorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)
    typical_lead_time_days: int = Field(ge=0, le=3650)
    imports_goods: bool = False


class VendorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)
    typical_lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    imports_goods: bool | None = None


class VendorView(BaseModel):
    id: UUID
    name: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    typical_lead_time_days: int
    imports_goods: bool
    archived_at: datetime | None


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=32)
    reorder_threshold: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    # Create may set the opening balance. Updates cannot. Stage 4 owns the ledger.
    current_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    unit_cost_currency: str | None = Field(default=None, min_length=3, max_length=3)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    reorder_threshold: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    unit_cost_currency: str | None = Field(default=None, min_length=3, max_length=3)
    clear_unit_cost: bool = False


class ProductView(BaseModel):
    id: UUID
    sku: str
    name: str
    unit: str
    current_stock: Decimal
    reorder_threshold: Decimal
    unit_cost: Decimal | None
    unit_cost_currency: str | None
    archived_at: datetime | None


class ProductVendorAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_id: UUID


class ProductVendorView(BaseModel):
    id: UUID
    product_id: UUID
    vendor_id: UUID
    role: VendorRole
    vendor_name: str
    vendor_archived_at: datetime | None
