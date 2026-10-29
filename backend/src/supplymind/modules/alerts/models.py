"""Alerts. One open or acknowledged row per workspace dedupe key."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import AlertStatus, AlertType, RiskBand, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin


class Alert(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_alerts_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_alerts_product",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "snapshot_id"],
            ["risk_snapshots.workspace_id", "risk_snapshots.id"],
            name="fk_alerts_snapshot",
        ),
        CheckConstraint(
            "(status <> 'open') OR (acknowledged_at IS NULL AND resolved_at IS NULL)",
            name="open_times",
        ),
        CheckConstraint(
            "(status <> 'acknowledged') OR (acknowledged_at IS NOT NULL AND resolved_at IS NULL)",
            name="acknowledged_times",
        ),
        CheckConstraint(
            "(status NOT IN ('resolved', 'auto_resolved')) OR (resolved_at IS NOT NULL)",
            name="resolved_times",
        ),
    )

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    alert_type: Mapped[AlertType] = mapped_column(
        pg_enum(AlertType, "ck_alerts_type"),
        nullable=False,
    )
    severity: Mapped[RiskBand] = mapped_column(
        pg_enum(RiskBand, "ck_alerts_severity"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        pg_enum(AlertStatus, "ck_alerts_status"),
        nullable=False,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)


Index(
    "uq_alerts_open_dedupe",
    Alert.workspace_id,
    Alert.dedupe_key,
    unique=True,
    postgresql_where=text("status IN ('open', 'acknowledged')"),
)
