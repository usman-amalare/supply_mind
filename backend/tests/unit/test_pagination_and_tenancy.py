from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from supplymind.core.ids import new_id
from supplymind.core.pagination import Page, PageParams
from supplymind.core.tenancy import TenantContext
from supplymind.db.repository import TenantRepository


def test_page_params_reject_out_of_range_and_unknown_fields() -> None:
    assert PageParams().page_size == 20
    with pytest.raises(ValidationError):
        PageParams(page=0)
    with pytest.raises(ValidationError):
        PageParams(page_size=101)
    with pytest.raises(ValidationError):
        PageParams.model_validate({"page": 1, "page_size": 20, "extra": True})


def test_page_envelope_shape() -> None:
    page = Page[str](items=["a"], page=1, page_size=20, total=1)
    assert page.model_dump() == {"items": ["a"], "page": 1, "page_size": 20, "total": 1}


def test_repository_requires_a_tenant_context() -> None:
    workspace_id = new_id()
    repo = TenantRepository(cast(Session, object()), TenantContext(workspace_id=workspace_id))
    assert repo.workspace_id == workspace_id
    with pytest.raises(TypeError):
        TenantRepository(cast(Session, object()), cast(TenantContext, None))
    with pytest.raises(TypeError):
        TenantContext(workspace_id=cast(UUID, "not-a-uuid"))
