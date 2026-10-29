"""Current workspace routes. The workspace id is not a parameter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from supplymind.api.deps import Auth, Db, current_request_id, require_csrf
from supplymind.api.schemas import error_responses
from supplymind.modules.identity.schemas import WorkspaceView
from supplymind.modules.workspaces.schemas import (
    WorkspacePatch,
    WorkspaceSettingsPatch,
    WorkspaceSettingsView,
)
from supplymind.modules.workspaces.service import WorkspaceService

router = APIRouter(dependencies=[Depends(require_csrf)])


def _service(request: Request, auth: Auth, db: Db) -> WorkspaceService:
    return WorkspaceService(
        db,
        auth.tenant,
        actor_id=auth.user_id,
        request_id=current_request_id(request),
    )


@router.get("/workspace", response_model=WorkspaceView, responses=error_responses(401, 403, 404))
def read_workspace(request: Request, auth: Auth, db: Db) -> WorkspaceView:
    return _service(request, auth, db).get_workspace()


@router.patch(
    "/workspace",
    response_model=WorkspaceView,
    responses=error_responses(401, 403, 404, 422),
)
def update_workspace(
    body: WorkspacePatch,
    request: Request,
    auth: Auth,
    db: Db,
) -> WorkspaceView:
    return _service(request, auth, db).rename(body.name)


@router.get(
    "/workspace/settings",
    response_model=WorkspaceSettingsView,
    responses=error_responses(401, 403, 404),
)
def read_workspace_settings(
    request: Request,
    auth: Auth,
    db: Db,
) -> WorkspaceSettingsView:
    return _service(request, auth, db).get_settings()


@router.patch(
    "/workspace/settings",
    response_model=WorkspaceSettingsView,
    responses=error_responses(401, 403, 404, 422),
)
def update_workspace_settings(
    body: WorkspaceSettingsPatch,
    request: Request,
    auth: Auth,
    db: Db,
) -> WorkspaceSettingsView:
    return _service(request, auth, db).replace_notification_prefs(body.notification_prefs)
