"""Identifier generation. UUID4 until the runtime provides UUID7. See D-004."""

from __future__ import annotations

from uuid import UUID, uuid4


def new_id() -> UUID:
    return uuid4()
