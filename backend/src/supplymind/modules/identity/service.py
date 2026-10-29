"""Registration, login, sessions, and password-reset tokens.

The raw session token leaves this service only so the router can set a cookie.
Password-reset tokens are returned only to a delivery adapter. The HTTP layer
discards that return value. Email delivery is not implemented.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplymind.clock import Clock
from supplymind.config import Settings
from supplymind.core.errors import AppError
from supplymind.core.ids import new_id
from supplymind.core.security import (
    dummy_password_check,
    hash_ip,
    hash_password,
    hash_token,
    make_password_hasher,
    new_token,
    password_needs_rehash,
    verify_password,
)
from supplymind.modules.audit.repository import AuditRepository
from supplymind.modules.identity.emails import normalize_email
from supplymind.modules.identity.models import PasswordResetToken, User
from supplymind.modules.identity.models import Session as SessionRecord
from supplymind.modules.identity.repository import AccountRepository
from supplymind.modules.workspaces.models import Workspace
from supplymind.modules.workspaces.repository import create_owner_workspace

_logger = logging.getLogger("supplymind.identity")

JsonObject = dict[str, object]


class AuditWriter(Protocol):
    def append(
        self,
        *,
        workspace_id: UUID | None,
        actor: str | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        before: JsonObject | None,
        after: JsonObject | None,
        request_id: str | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AuthResult:
    user_id: UUID
    email: str
    workspace_id: UUID
    workspace_name: str
    industry: str | None
    size_band: str | None
    timezone: str
    currency: str
    onboarding_step: str
    onboarding_completed_at: datetime | None
    session_id: UUID
    session_token: str
    csrf_token: str


class IdentityService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        *,
        audit: AuditWriter | None = None,
    ) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._accounts = AccountRepository(session)
        self._audit: AuditWriter = audit if audit is not None else AuditRepository(session)
        self._hasher = make_password_hasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
        )

    def register(
        self,
        *,
        email: str,
        password: str,
        workspace_name: str,
        user_agent: str | None,
        ip: str | None,
        request_id: str | None,
        presented_session_token: str | None = None,
    ) -> AuthResult:
        canonical = _email_or_error(email)
        name = _workspace_name(workspace_name)
        password_hash = hash_password(password, self._hasher)
        user = User(id=new_id(), email=canonical, password_hash=password_hash, is_active=True)
        try:
            self._accounts.add_user(user)
            workspace, _membership, _settings_row = create_owner_workspace(
                self._session,
                user_id=user.id,
                name=name,
            )
            self._session.flush()
            result = self._issue_session(
                user=user,
                workspace=workspace,
                user_agent=user_agent,
                ip=ip,
                request_id=request_id,
                presented_session_token=presented_session_token,
            )
            self._audit.append(
                workspace_id=workspace.id,
                actor=str(user.id),
                action="user_registered",
                entity_type="user",
                entity_id=user.id,
                before=None,
                after={"workspace_id": str(workspace.id)},
                request_id=request_id,
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if _is_duplicate_email(exc):
                raise AppError(
                    "registration_conflict",
                    "An account could not be created with those details.",
                    status_code=409,
                ) from None
            _logger.error("registration integrity error")
            raise AppError(
                "internal_error",
                "Internal server error",
                status_code=500,
            ) from None
        except Exception:
            self._session.rollback()
            raise
        return result

    def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip: str | None,
        request_id: str | None,
        presented_session_token: str | None,
    ) -> AuthResult:
        canonical = _email_or_error(email)
        user = self._accounts.get_user_by_email(canonical)
        if user is None or not user.is_active:
            self._spend_dummy(password)
            self._audit_login_failed(user, request_id)
            self._session.commit()
            raise _invalid_credentials()
        if not verify_password(password, user.password_hash, self._hasher):
            self._audit_login_failed(user, request_id)
            self._session.commit()
            raise _invalid_credentials()
        if password_needs_rehash(user.password_hash, self._hasher):
            user.password_hash = hash_password(password, self._hasher)
        workspace = self._workspace_for(user.id)
        if workspace is None:
            self._audit_login_failed(user, request_id)
            self._session.commit()
            raise _invalid_credentials()
        try:
            result = self._issue_session(
                user=user,
                workspace=workspace,
                user_agent=user_agent,
                ip=ip,
                request_id=request_id,
                presented_session_token=presented_session_token,
            )
            self._audit.append(
                workspace_id=workspace.id,
                actor=str(user.id),
                action="login_succeeded",
                entity_type="session",
                entity_id=result.session_id,
                before=None,
                after=None,
                request_id=request_id,
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return result

    def logout(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        workspace_id: UUID,
        request_id: str | None,
    ) -> None:
        record = self._accounts.get_session(session_id)
        if record is None or record.user_id != user_id:
            raise _unauthenticated()
        now = self._clock.now()
        if record.revoked_at is None:
            record.revoked_at = now
        self._audit.append(
            workspace_id=workspace_id,
            actor=str(user_id),
            action="logout",
            entity_type="session",
            entity_id=session_id,
            before=None,
            after=None,
            request_id=request_id,
        )
        self._session.commit()

    def revoke_all_sessions(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        request_id: str | None,
    ) -> None:
        revoked = self._accounts.revoke_all_for_user(user_id, self._clock.now())
        self._audit.append(
            workspace_id=workspace_id,
            actor=str(user_id),
            action="sessions_revoked",
            entity_type="user",
            entity_id=user_id,
            before=None,
            after={"revoked": revoked},
            request_id=request_id,
        )
        self._session.commit()

    def rotate_csrf(self, session_id: UUID) -> str:
        record = self._accounts.get_session(session_id)
        if record is None or record.revoked_at is not None:
            raise _unauthenticated()
        raw = new_token()
        record.csrf_token_hash = hash_token(raw)
        self._session.commit()
        return raw

    def prepare_password_reset(self, *, email: str, request_id: str | None) -> str | None:
        """Store a single-use token and return it for a delivery adapter.

        Returns None when no active account exists. Callers that speak HTTP
        must ignore the return value. This method does not send email.
        """
        self._spend_dummy("password-reset-request")
        try:
            canonical = normalize_email(email)
        except ValueError:
            self._audit_reset_requested(None, request_id)
            self._session.commit()
            return None
        user = self._accounts.get_user_by_email(canonical)
        if user is None or not user.is_active:
            self._audit_reset_requested(None, request_id)
            self._session.commit()
            return None
        now = self._clock.now()
        raw = new_token()
        self._accounts.invalidate_unused_resets(user.id, now)
        self._accounts.add_reset_token(
            PasswordResetToken(
                id=new_id(),
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=now + timedelta(minutes=self._settings.password_reset_ttl_minutes),
            )
        )
        self._audit_reset_requested(user.id, request_id)
        self._session.commit()
        return raw

    def confirm_password_reset(
        self,
        *,
        token: str,
        password: str,
        request_id: str | None,
    ) -> None:
        now = self._clock.now()
        record = self._accounts.get_reset_by_hash(hash_token(token))
        user = self._accounts.get_user(record.user_id) if record is not None else None
        if (
            record is None
            or record.used_at is not None
            or record.expires_at <= now
            or user is None
            or not user.is_active
        ):
            raise _reset_rejected()
        try:
            user.password_hash = hash_password(password, self._hasher)
            record.used_at = now
            self._accounts.revoke_all_for_user(user.id, now)
            self._audit.append(
                workspace_id=None,
                actor=str(user.id),
                action="password_reset_completed",
                entity_type="user",
                entity_id=user.id,
                before=None,
                after=None,
                request_id=request_id,
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _issue_session(
        self,
        *,
        user: User,
        workspace: Workspace,
        user_agent: str | None,
        ip: str | None,
        request_id: str | None,
        presented_session_token: str | None,
    ) -> AuthResult:
        now = self._clock.now()
        if presented_session_token:
            self._accounts.revoke_by_token_hash(hash_token(presented_session_token), now)
        raw_session = new_token()
        raw_csrf = new_token()
        secret = self._settings.app_secret.get_secret_value()
        record = SessionRecord(
            id=new_id(),
            user_id=user.id,
            token_hash=hash_token(raw_session),
            csrf_token_hash=hash_token(raw_csrf),
            expires_at=now + timedelta(hours=self._settings.session_absolute_timeout_hours),
            last_seen_at=now,
            user_agent=_user_agent(user_agent),
            ip_hash=hash_ip(ip, secret) if ip else None,
        )
        self._accounts.add_session(record)
        self._session.flush()
        self._audit.append(
            workspace_id=workspace.id,
            actor=str(user.id),
            action="session_created",
            entity_type="session",
            entity_id=record.id,
            before=None,
            after=None,
            request_id=request_id,
        )
        return AuthResult(
            user_id=user.id,
            email=user.email,
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            industry=workspace.industry,
            size_band=workspace.size_band,
            timezone=workspace.timezone,
            currency=workspace.currency,
            onboarding_step=workspace.onboarding_step.value,
            onboarding_completed_at=workspace.onboarding_completed_at,
            session_id=record.id,
            session_token=raw_session,
            csrf_token=raw_csrf,
        )

    def _workspace_for(self, user_id: UUID) -> Workspace | None:
        memberships = self._accounts.memberships_for_user(user_id)
        if len(memberships) != 1:
            return None
        return self._session.get(Workspace, memberships[0].workspace_id)

    def _spend_dummy(self, password: str) -> None:
        dummy_password_check(
            password,
            self._hasher,
            time_cost=self._settings.argon2_time_cost,
            memory_cost=self._settings.argon2_memory_cost,
            parallelism=self._settings.argon2_parallelism,
        )

    def _audit_login_failed(self, user: User | None, request_id: str | None) -> None:
        self._audit.append(
            workspace_id=None,
            actor=None,
            action="login_failed",
            entity_type="user",
            entity_id=user.id if user is not None else None,
            before=None,
            after=None,
            request_id=request_id,
        )

    def _audit_reset_requested(self, user_id: UUID | None, request_id: str | None) -> None:
        self._audit.append(
            workspace_id=None,
            actor=str(user_id) if user_id is not None else None,
            action="password_reset_requested",
            entity_type="user",
            entity_id=user_id,
            before=None,
            after=None,
            request_id=request_id,
        )


def _email_or_error(value: str) -> str:
    try:
        return normalize_email(value)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": "email"},
        ) from None


def _workspace_name(value: str) -> str:
    name = value.strip()
    if not name or len(name) > 200:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": "workspace_name"},
        )
    return name


def _user_agent(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:512]


def _is_duplicate_email(exc: IntegrityError) -> bool:
    orig = exc.orig
    diag = getattr(orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    if name == "uq_users_lower_email":
        return True
    text = str(orig)
    return "uq_users_lower_email" in text


def _invalid_credentials() -> AppError:
    return AppError(
        "invalid_credentials",
        "Email or password is incorrect.",
        status_code=401,
    )


def _unauthenticated() -> AppError:
    return AppError("unauthenticated", "Authentication is required.", status_code=401)


def _reset_rejected() -> AppError:
    return AppError(
        "reset_rejected",
        "Password reset could not be completed.",
        status_code=400,
    )
