from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from supplymind.clock import FrozenClock, SystemClock
from supplymind.core.rate_limit import InMemoryRateLimiter


def test_system_clock_is_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_freezegun_controls_the_system_clock() -> None:
    with freeze_time("2026-01-15T12:00:00+00:00"):
        now = SystemClock().now()
    assert now == datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def test_frozen_clock_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError):
        FrozenClock(datetime(2026, 1, 1))


def test_rate_limiter_expires_with_the_injected_clock() -> None:
    clock = FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))
    limiter = InMemoryRateLimiter(clock)
    window = timedelta(seconds=10)
    assert limiter.allow("login:1", limit=2, window=window)
    assert limiter.allow("login:1", limit=2, window=window)
    assert not limiter.allow("login:1", limit=2, window=window)
    clock.advance(timedelta(seconds=10))
    assert limiter.allow("login:1", limit=2, window=window)
    assert limiter.allow("other", limit=2, window=window)
