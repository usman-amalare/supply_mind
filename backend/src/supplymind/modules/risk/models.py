"""Stored risk results. Null probability means the engine withheld a number."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import ConfidenceLevel, RiskBand, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin

JsonObject = dict[str, object]


class RiskSnapshot(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "risk_snapshots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_risk_snapshots_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "product_id",
            "inputs_hash",
            name="uq_risk_snapshots_inputs",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_risk_snapshots_product",
        ),
        CheckConstraint(
            "stockout_probability IS NULL OR "
            "(stockout_probability >= 0 AND stockout_probability <= 1)",
            name="probability_range",
        ),
        CheckConstraint(
            "days_of_cover IS NULL OR days_of_cover >= 0",
            name="days_of_cover_non_negative",
        ),
    )

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    stockout_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    risk_band: Mapped[RiskBand | None] = mapped_column(pg_enum(RiskBand, "ck_risk_snapshots_band"))
    days_of_cover: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    confidence: Mapped[ConfidenceLevel | None] = mapped_column(
        pg_enum(ConfidenceLevel, "ck_risk_snapshots_confidence")
    )
    evidence: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    contributions: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    data_quality: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
