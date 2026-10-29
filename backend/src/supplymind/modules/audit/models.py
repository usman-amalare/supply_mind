"""Audit log. workspace_id may be null for account events that have no workspace (D-006)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

JsonObject = dict[str, object]


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_log"

    workspace_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id"), index=True
    )
    actor: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    before: Mapped[JsonObject | None] = mapped_column(JSONB)
    after: Mapped[JsonObject | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(64))


Index("ix_audit_log_workspace_created", AuditLog.workspace_id, AuditLog.created_at)
