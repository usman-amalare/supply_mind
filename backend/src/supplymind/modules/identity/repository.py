"""Account persistence. Users and sessions are not workspace-scoped.

Membership lookup here establishes the tenant from the authenticated user.
It does not accept a workspace id from the caller.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from supplymind.modules.identity.models import PasswordResetToken, User
from supplymind.modules.identity.models import Session as SessionRecord
from supplymind.modules.workspaces.models import Membership


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_user(self, user: User) -> User:
        self._session.add(user)
        return user

    def get_user_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def get_user(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def add_session(self, record: SessionRecord) -> SessionRecord:
        self._session.add(record)
        return record

    def get_session(self, session_id: UUID) -> SessionRecord | None:
        return self._session.get(SessionRecord, session_id)

    def get_session_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        return self._session.scalar(
            select(SessionRecord).where(SessionRecord.token_hash == token_hash)
        )

    def revoke_by_token_hash(self, token_hash: str, revoked_at: datetime) -> None:
        record = self.get_session_by_token_hash(token_hash)
        if record is not None and record.revoked_at is None:
            record.revoked_at = revoked_at

    def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> int:
        active = self._session.scalar(
            select(func.count())
            .select_from(SessionRecord)
            .where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
        )
        self._session.execute(
            update(SessionRecord)
            .where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        return int(active or 0)

    def memberships_for_user(self, user_id: UUID) -> list[Membership]:
        rows = self._session.scalars(select(Membership).where(Membership.user_id == user_id))
        return list(rows)

    def add_reset_token(self, token: PasswordResetToken) -> PasswordResetToken:
        self._session.add(token)
        return token

    def get_reset_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self._session.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )

    def invalidate_unused_resets(self, user_id: UUID, used_at: datetime) -> None:
        self._session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=used_at)
        )
