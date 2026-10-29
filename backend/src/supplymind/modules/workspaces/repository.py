"""Workspace persistence.

`create_owner_workspace` is the registration bootstrap. There is no tenant to
pass yet; the workspace id is generated here and is never taken from the client.

Every later read or update goes through `WorkspaceRepository`, which requires
a `TenantContext` and ignores any other workspace id.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from supplymind.db.enums import MembershipRole, OnboardingStep
from supplymind.db.repository import TenantRepository
from supplymind.modules.workspaces.models import (
    Membership,
    Workspace,
    WorkspaceSettings,
    default_alert_thresholds,
    default_notification_prefs,
)


def create_owner_workspace(
    session: Session,
    *,
    user_id: UUID,
    name: str,
) -> tuple[Workspace, Membership, WorkspaceSettings]:
    workspace = Workspace(
        name=name,
        timezone="Africa/Lagos",
        currency="NGN",
        onboarding_step=OnboardingStep.COMPANY,
    )
    session.add(workspace)
    session.flush()
    membership = Membership(
        workspace_id=workspace.id,
        user_id=user_id,
        role=MembershipRole.OWNER,
    )
    settings = WorkspaceSettings(
        workspace_id=workspace.id,
        enabled_risk_factors=[],
        alert_thresholds=default_alert_thresholds(),
        notification_prefs=default_notification_prefs(),
    )
    session.add(membership)
    session.add(settings)
    return workspace, membership, settings


class WorkspaceRepository(TenantRepository):
    def get_workspace(self) -> Workspace | None:
        return self._session.get(Workspace, self.workspace_id)

    def get_settings(self) -> WorkspaceSettings | None:
        return self._session.scalar(
            select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == self.workspace_id)
        )

    def rename(self, name: str) -> Workspace | None:
        workspace = self.get_workspace()
        if workspace is None:
            return None
        workspace.name = name
        return workspace

    def replace_notification_prefs(self, prefs: dict[str, object]) -> WorkspaceSettings | None:
        row = self.get_settings()
        if row is None:
            return None
        row.notification_prefs = prefs
        return row
