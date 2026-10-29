"""Workspace rows. Alert-threshold defaults are the Section 10.4 and 10.7 numbers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import MembershipRole, OnboardingStep, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin

JsonObject = dict[str, object]


def default_alert_thresholds() -> JsonObject:
    return {
        "medium": 0.25,
        "high": 0.50,
        "critical": 0.80,
        "resolve_hysteresis": 0.05,
    }


def default_notification_prefs() -> JsonObject:
    return {"recipient_emails": [], "cooldown_hours": 24}


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) > 0", name="name_present"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_code"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(120))
    size_band: Mapped[str | None] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Africa/Lagos",
        server_default=text("'Africa/Lagos'"),
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
    )
    onboarding_step: Mapped[OnboardingStep] = mapped_column(
        pg_enum(OnboardingStep, "ck_workspaces_onboarding_step"),
        nullable=False,
        default=OnboardingStep.COMPANY,
        server_default=text("'company'"),
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Membership(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_memberships_workspace_id"),
        UniqueConstraint("user_id", "workspace_id", name="uq_memberships_user_workspace"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        pg_enum(MembershipRole, "ck_memberships_role"),
        nullable=False,
    )


Index(
    "uq_memberships_one_owner",
    Membership.workspace_id,
    unique=True,
    postgresql_where=text("role = 'owner'"),
)


class WorkspaceSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_settings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_workspace_settings_workspace_pair"),
        CheckConstraint(
            "risk_recalculation_interval_minutes >= 1",
            name="recalc_interval_positive",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
        unique=True,
    )
    enabled_risk_factors: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    alert_thresholds: Mapped[JsonObject] = mapped_column(
        JSONB,
        nullable=False,
        default=default_alert_thresholds,
        server_default=text(
            '\'{"medium": 0.25, "high": 0.50, "critical": 0.80, '
            '"resolve_hysteresis": 0.05}\'::jsonb'
        ),
    )
    notification_prefs: Mapped[JsonObject] = mapped_column(
        JSONB,
        nullable=False,
        default=default_notification_prefs,
        server_default=text("""'{"recipient_emails": [], "cooldown_hours": 24}'::jsonb"""),
    )
    ai_monthly_token_cap: Mapped[int | None] = mapped_column(Integer)
    ai_monthly_cost_cap: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    risk_recalculation_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default=text("60")
    )
    fx_delay_beta: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    fx_rate_type: Mapped[str | None] = mapped_column(String(64))
