"""Shared primary key and timestamp columns."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.core.ids import new_id


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_id)


class WorkspaceIdMixin:
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
