"""Explanations and monthly usage. Caps stay null until a product limit is chosen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import ExplanationSource, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin

JsonObject = dict[str, object]


class Explanation(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "explanations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_explanations_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "snapshot_id",
            "input_hash",
            name="uq_explanations_snapshot_input",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "snapshot_id"],
            ["risk_snapshots.workspace_id", "risk_snapshots.id"],
            name="fk_explanations_snapshot",
        ),
        CheckConstraint(
            "prompt_tokens IS NULL OR prompt_tokens >= 0", name="prompt_tokens_non_negative"
        ),
        CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name="completion_tokens_non_negative",
        ),
        CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="estimated_cost_non_negative",
        ),
    )

    snapshot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    source: Mapped[ExplanationSource] = mapped_column(
        pg_enum(ExplanationSource, "ck_explanations_source"),
        nullable=False,
    )
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))


class AiUsage(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage"
    __table_args__ = (
        UniqueConstraint("workspace_id", "period", name="uq_ai_usage_period"),
        CheckConstraint("EXTRACT(DAY FROM period) = 1", name="period_is_month_start"),
        CheckConstraint("requests >= 0", name="requests_non_negative"),
        CheckConstraint("prompt_tokens >= 0", name="prompt_tokens_non_negative"),
        CheckConstraint("completion_tokens >= 0", name="completion_tokens_non_negative"),
        CheckConstraint("estimated_cost >= 0", name="estimated_cost_non_negative"),
        CheckConstraint("blocked_requests >= 0", name="blocked_requests_non_negative"),
    )

    period: Mapped[date] = mapped_column(Date, nullable=False)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    blocked_requests: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
