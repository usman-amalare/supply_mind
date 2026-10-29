"""Notification attempts. Delivery status values are not constrained yet (D-007)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import NotificationEvent, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin


class Notification(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_notifications_workspace_id"),
        UniqueConstraint(
            "alert_id",
            "event",
            "recipient",
            name="uq_notifications_alert_event_recipient",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "alert_id"],
            ["alerts.workspace_id", "alerts.id"],
            name="fk_notifications_alert",
        ),
    )

    alert_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event: Mapped[NotificationEvent] = mapped_column(
        pg_enum(NotificationEvent, "ck_notifications_event"),
        nullable=False,
    )
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
