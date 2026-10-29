"""Injectable clock. Business code uses this instead of datetime.now."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current timezone-aware UTC instant."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Test clock. Advance it explicitly; it does not read the wall clock."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime")
        self._instant = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._instant

    def advance(self, delta: timedelta) -> None:
        self._instant += delta
