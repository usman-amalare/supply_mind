"""Base repository. A method path without TenantContext is a defect."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from supplymind.core.tenancy import TenantContext


class TenantRepository:
    def __init__(self, session: Session, tenant: TenantContext) -> None:
        if not isinstance(tenant, TenantContext):
            raise TypeError("A TenantContext is required")
        self._session = session
        self._tenant = tenant

    @property
    def workspace_id(self) -> UUID:
        return self._tenant.workspace_id
