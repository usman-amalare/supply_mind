"""PostgreSQL-backed jobs. workspace_id is null only for global work such as FX refresh."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import JobStatus, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

JsonObject = dict[str, object]


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        CheckConstraint(
            "(locked_at IS NULL) = (locked_by IS NULL)",
            name="lock_pair",
        ),
    )

    workspace_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id"), index=True
    )
    job_type: Mapped[str] = mapped_column("type", String(64), nullable=False)
    payload: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(200))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[JobStatus] = mapped_column(pg_enum(JobStatus, "ck_jobs_status"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_by: Mapped[str | None] = mapped_column(String(120))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))


Index(
    "uq_jobs_active_dedupe",
    Job.dedupe_key,
    unique=True,
    postgresql_where=text("status IN ('pending', 'running')"),
)
Index(
    "ix_jobs_pending_run_at",
    Job.run_at,
    postgresql_where=text("status = 'pending'"),
)
