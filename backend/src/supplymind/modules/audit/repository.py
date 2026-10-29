"""Append-only audit writes.

Account events may have a null workspace id (D-006). This repository has no
update or delete methods. It does not accept a client-supplied tenant: callers
pass the workspace id resolved from the session, or None when there is no
workspace. Reads of tenant audit rows are not part of this stage.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from supplymind.modules.audit.models import AuditLog

JsonObject = dict[str, object]


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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
    ) -> None:
        self._session.add(
            AuditLog(
                workspace_id=workspace_id,
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before=before,
                after=after,
                request_id=request_id,
            )
        )
