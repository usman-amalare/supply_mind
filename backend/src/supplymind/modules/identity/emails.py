"""Email canonicalisation. Stored values match the case-insensitive unique index."""

from __future__ import annotations

import re

_LOCAL = re.compile(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+\Z")
_DOMAIN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\Z"
)


def normalize_email(value: str) -> str:
    """Return a lowercase email, or raise ValueError without echoing the input."""
    email = value.strip().casefold()
    if len(email) < 3 or len(email) > 320 or any(char.isspace() for char in email):
        raise ValueError("invalid email")
    local, separator, domain = email.partition("@")
    if separator != "@" or email.count("@") != 1:
        raise ValueError("invalid email")
    if _LOCAL.fullmatch(local) is None or _DOMAIN.fullmatch(domain) is None:
        raise ValueError("invalid email")
    return email
