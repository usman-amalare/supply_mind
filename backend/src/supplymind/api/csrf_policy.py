"""CSRF exceptions for routes that cannot yet present a session-bound token.

Register, login, and password reset run before a browser has a CSRF token for
the session they create or recover. Every other unsafe `/api/v1` route must
depend on `require_csrf`. The route-coverage test fails if a new mutation is
neither listed here nor protected.
"""

from __future__ import annotations

CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/password-resets",
        "/api/v1/auth/password-resets/confirm",
    }
)

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
