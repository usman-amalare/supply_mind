"""In-process rate limiter.

Single-process only. A second API process would not share counters.
That limitation is accepted for v1 in the master prompt; Redis is not used.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from supplymind.clock import Clock


class InMemoryRateLimiter:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._events: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, limit: int, window: timedelta) -> bool:
        if not key:
            raise ValueError("rate limit key is required")
        if limit < 1:
            raise ValueError("rate limit must be at least 1")
        if window <= timedelta(0):
            raise ValueError("rate limit window must be positive")
        now = self._clock.now()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetimes")
        cutoff = now - window
        with self._lock:
            recent = [instant for instant in self._events.get(key, []) if instant > cutoff]
            if len(recent) >= limit:
                self._events[key] = recent
                return False
            recent.append(now)
            self._events[key] = recent
            return True
