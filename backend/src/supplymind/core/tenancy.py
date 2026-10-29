"""Tenant context. Repositories must receive one; a missing context is a defect."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantContext:
    workspace_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_id, UUID):
            raise TypeError("workspace_id must be a UUID")
