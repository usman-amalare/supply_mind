"""Request dependencies. Workspace ids come from the session membership, not the client."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from supplymind.api.csrf_policy import UNSAFE_METHODS
from supplymind.config import Settings
from supplymind.core.errors import AppError
from supplymind.core.rate_limit import InMemoryRateLimiter
from supplymind.core.security import hash_token, token_matches
from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import MembershipRole
from supplymind.db.session import make_session_factory
from supplymind.modules.identity.repository import AccountRepository
from supplymind.modules.workspaces.models import Workspace


class AuthContext:
    """Authenticated user and the single owner workspace resolved for this session."""

    def __init__(
        self,
        *,
        user_id: UUID,
        email: str,
        session_id: UUID,
        workspace_id: UUID,
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.session_id = session_id
        self.workspace_id = workspace_id
        self.tenant = TenantContext(workspace_id)


def get_db(request: Request) -> Iterator[Session]:
    stored = getattr(request.app.state, "session_factory", None)
    if stored is None:
        factory = make_session_factory(request.app.state.engine)
        request.app.state.session_factory = factory
    else:
        factory = cast(sessionmaker[Session], stored)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


Db = Annotated[Session, Depends(get_db)]


def session_cookie_value(request: Request) -> str | None:
    settings: Settings = request.app.state.settings
    raw = request.cookies.get(settings.session_cookie_name)
    if not isinstance(raw, str):
        return None
    token = raw.strip()
    return token or None


def client_ip(request: Request) -> str | None:
    client = request.client
    if client is None:
        return None
    host = client.host.strip()
    return host or None


def current_request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return None


def enforce_rate_limit(request: Request, bucket: str) -> None:
    settings: Settings = request.app.state.settings
    limiter: InMemoryRateLimiter = request.app.state.rate_limiter
    host = client_ip(request) or "unknown"
    allowed = limiter.allow(
        f"{bucket}:{host}",
        limit=settings.auth_rate_limit_attempts,
        window=timedelta(seconds=settings.auth_rate_limit_window_seconds),
    )
    if not allowed:
        raise AppError(
            "rate_limited",
            "Too many attempts. Try again later.",
            status_code=429,
        )


def limit_signup(request: Request) -> None:
    enforce_rate_limit(request, "signup")


def limit_login(request: Request) -> None:
    enforce_rate_limit(request, "login")


def limit_password_reset(request: Request) -> None:
    enforce_rate_limit(request, "password-reset")


def get_auth_context(request: Request, db: Db) -> AuthContext:
    settings: Settings = request.app.state.settings
    raw = session_cookie_value(request)
    if raw is None:
        raise _unauthenticated()
    accounts = AccountRepository(db)
    record = accounts.get_session_by_token_hash(hash_token(raw))
    now = request.app.state.clock.now()
    if record is None or record.revoked_at is not None or record.expires_at <= now:
        raise _unauthenticated()
    idle = timedelta(hours=settings.session_idle_timeout_hours)
    if now - record.last_seen_at >= idle:
        raise _unauthenticated()
    user = accounts.get_user(record.user_id)
    if user is None or not user.is_active:
        raise _unauthenticated()
    memberships = accounts.memberships_for_user(user.id)
    if len(memberships) != 1 or memberships[0].role != MembershipRole.OWNER:
        raise _workspace_unavailable()
    workspace = db.get(Workspace, memberships[0].workspace_id)
    if workspace is None:
        raise _workspace_unavailable()
    record.last_seen_at = now
    return AuthContext(
        user_id=user.id,
        email=user.email,
        session_id=record.id,
        workspace_id=workspace.id,
    )


Auth = Annotated[AuthContext, Depends(get_auth_context)]


def require_csrf(request: Request, auth: Auth, db: Db) -> None:
    """Reject cookie-authenticated mutations that lack this session's CSRF header."""
    if request.method not in UNSAFE_METHODS:
        return
    settings: Settings = request.app.state.settings
    presented = request.headers.get(settings.csrf_header_name, "").strip()
    record = AccountRepository(db).get_session(auth.session_id)
    if record is None or not token_matches(presented, record.csrf_token_hash):
        raise AppError(
            "csrf_invalid",
            "CSRF token is missing or invalid.",
            status_code=403,
        )


def _unauthenticated() -> AppError:
    return AppError("unauthenticated", "Authentication is required.", status_code=401)


def _workspace_unavailable() -> AppError:
    return AppError(
        "workspace_unavailable",
        "Workspace access is not available.",
        status_code=403,
    )
