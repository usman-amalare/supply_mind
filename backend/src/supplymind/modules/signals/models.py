"""Global signal tables. They intentionally have no workspace_id.

No seasonal dates are seeded here. Dates must be cited or marked needs_verification.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from supplymind.db.base import Base
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class FxRate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint(
            "pair",
            "rate_type",
            "observed_on",
            "source",
            name="uq_fx_rates_observation",
        ),
        CheckConstraint("pair = 'USD/NGN'", name="usd_ngn_only"),
        CheckConstraint("rate > 0", name="rate_positive"),
        CheckConstraint("char_length(btrim(rate_type)) > 0", name="rate_type_present"),
        CheckConstraint("char_length(btrim(source)) > 0", name="source_present"),
    )

    pair: Mapped[str] = mapped_column(String(16), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    rate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_ref: Mapped[str | None] = mapped_column(String(500))


class SeasonalEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seasonal_events"
    __table_args__ = (
        UniqueConstraint(
            "code",
            "region",
            "starts_on",
            name="uq_seasonal_events_occurrence",
        ),
        CheckConstraint("ends_on >= starts_on", name="event_order"),
        CheckConstraint("char_length(btrim(source_note)) > 0", name="source_note_present"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    source_note: Mapped[str] = mapped_column(Text, nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    rule_note: Mapped[str | None] = mapped_column(Text)
