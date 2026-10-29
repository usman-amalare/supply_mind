"""Current-workspace reads and the narrow settings surface."""

from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from supplymind.core.errors import AppError
from supplymind.core.tenancy import TenantContext
from supplymind.modules.audit.repository import AuditRepository
from supplymind.modules.identity.emails import normalize_email
from supplymind.modules.identity.schemas import WorkspaceView
from supplymind.modules.workspaces.repository import WorkspaceRepository
from supplymind.modules.workspaces.schemas import (
    NotificationPrefs,
    WorkspaceSettingsView,
)

_NOT_FOUND = AppError("not_found", "Resource not found.", status_code=404)


class WorkspaceService:
    def __init__(
        self,
        session: Session,
        tenant: TenantContext,
        *,
        actor_id: UUID,
        request_id: str | None,
    ) -> None:
        self._session = session
        self._repo = WorkspaceRepository(session, tenant)
        self._audit = AuditRepository(session)
        self._actor_id = actor_id
        self._request_id = request_id
        self._tenant = tenant

    def get_workspace(self) -> WorkspaceView:
        workspace = self._repo.get_workspace()
        if workspace is None:
            raise _NOT_FOUND
        return WorkspaceView(
            id=workspace.id,
            name=workspace.name,
            industry=workspace.industry,
            size_band=workspace.size_band,
            timezone=workspace.timezone,
            currency=workspace.currency,
            onboarding_step=workspace.onboarding_step.value,
            onboarding_completed_at=workspace.onboarding_completed_at,
        )

    def rename(self, name: str) -> WorkspaceView:
        cleaned = name.strip()
        if not cleaned or len(cleaned) > 200:
            raise AppError(
                "validation_error",
                "Request validation failed",
                status_code=422,
                details={"field": "name"},
            )
        workspace = self._repo.get_workspace()
        if workspace is None:
            raise _NOT_FOUND
        previous = workspace.name
        workspace.name = cleaned
        self._audit.append(
            workspace_id=self._tenant.workspace_id,
            actor=str(self._actor_id),
            action="workspace_updated",
            entity_type="workspace",
            entity_id=workspace.id,
            before={"name": previous},
            after={"name": cleaned},
            request_id=self._request_id,
        )
        self._session.commit()
        return self.get_workspace()

    def get_settings(self) -> WorkspaceSettingsView:
        return WorkspaceSettingsView(notification_prefs=self._prefs_or_404())

    def replace_notification_prefs(self, prefs: NotificationPrefs) -> WorkspaceSettingsView:
        emails = _recipients(prefs.recipient_emails)
        current = self._repo.get_settings()
        if current is None:
            raise _NOT_FOUND
        previous = _read_prefs(current.notification_prefs)
        stored = {"recipient_emails": emails, "cooldown_hours": prefs.cooldown_hours}
        updated = self._repo.replace_notification_prefs(stored)
        if updated is None:
            raise _NOT_FOUND
        self._audit.append(
            workspace_id=self._tenant.workspace_id,
            actor=str(self._actor_id),
            action="workspace_settings_updated",
            entity_type="workspace_settings",
            entity_id=updated.id,
            before={
                "recipient_emails": previous.recipient_emails,
                "cooldown_hours": previous.cooldown_hours,
            },
            after={"recipient_emails": emails, "cooldown_hours": prefs.cooldown_hours},
            request_id=self._request_id,
        )
        self._session.commit()
        return WorkspaceSettingsView(
            notification_prefs=NotificationPrefs(
                recipient_emails=emails,
                cooldown_hours=prefs.cooldown_hours,
            )
        )

    def _prefs_or_404(self) -> NotificationPrefs:
        row = self._repo.get_settings()
        if row is None:
            raise _NOT_FOUND
        return _read_prefs(row.notification_prefs)


def _recipients(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        try:
            email = normalize_email(value)
        except ValueError:
            raise AppError(
                "validation_error",
                "Request validation failed",
                status_code=422,
                details={"field": "recipient_emails"},
            ) from None
        if email not in seen:
            seen.append(email)
    return seen


def _read_prefs(raw: object) -> NotificationPrefs:
    if not isinstance(raw, dict):
        raise _NOT_FOUND
    emails = raw.get("recipient_emails")
    hours = raw.get("cooldown_hours")
    if not isinstance(emails, list) or not all(isinstance(item, str) for item in emails):
        raise _NOT_FOUND
    if type(hours) is not int:
        raise _NOT_FOUND
    try:
        return NotificationPrefs(recipient_emails=list(emails), cooldown_hours=hours)
    except ValidationError:
        raise _NOT_FOUND from None
