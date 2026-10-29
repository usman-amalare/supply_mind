"""Catalog HTTP routes. Workspace id is never a path or body parameter."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from supplymind.api.deps import Auth, Db, current_request_id, require_csrf
from supplymind.api.schemas import error_responses
from supplymind.core.pagination import Page
from supplymind.db.enums import VendorRole
from supplymind.modules.catalog.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductVendorAssign,
    ProductVendorView,
    ProductView,
    VendorCreate,
    VendorUpdate,
    VendorView,
)
from supplymind.modules.catalog.service import CatalogService

router = APIRouter(dependencies=[Depends(require_csrf)])


def _service(request: Request, auth: Auth, db: Db) -> CatalogService:
    return CatalogService(
        db,
        auth.tenant,
        request.app.state.clock,
        actor_id=auth.user_id,
        request_id=current_request_id(request),
    )


@router.post(
    "/vendors",
    status_code=201,
    response_model=VendorView,
    responses=error_responses(401, 403, 422),
)
def create_vendor(body: VendorCreate, request: Request, auth: Auth, db: Db) -> VendorView:
    return _service(request, auth, db).create_vendor(body)


@router.get(
    "/vendors",
    response_model=Page[VendorView],
    responses=error_responses(401, 403, 422),
)
def list_vendors(
    request: Request,
    auth: Auth,
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_archived: Annotated[bool, Query()] = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[VendorView]:
    return _service(request, auth, db).list_vendors(
        page=page,
        page_size=page_size,
        include_archived=include_archived,
        query=q,
    )


@router.get(
    "/vendors/{vendor_id}",
    response_model=VendorView,
    responses=error_responses(401, 403, 404),
)
def read_vendor(vendor_id: UUID, request: Request, auth: Auth, db: Db) -> VendorView:
    return _service(request, auth, db).get_vendor(vendor_id)


@router.patch(
    "/vendors/{vendor_id}",
    response_model=VendorView,
    responses=error_responses(401, 403, 404, 422),
)
def update_vendor(
    vendor_id: UUID,
    body: VendorUpdate,
    request: Request,
    auth: Auth,
    db: Db,
) -> VendorView:
    return _service(request, auth, db).update_vendor(vendor_id, body)


@router.post(
    "/vendors/{vendor_id}/archive",
    response_model=VendorView,
    responses=error_responses(401, 403, 404, 409),
)
def archive_vendor(vendor_id: UUID, request: Request, auth: Auth, db: Db) -> VendorView:
    return _service(request, auth, db).archive_vendor(vendor_id)


@router.post(
    "/products",
    status_code=201,
    response_model=ProductView,
    responses=error_responses(401, 403, 409, 422),
)
def create_product(body: ProductCreate, request: Request, auth: Auth, db: Db) -> ProductView:
    return _service(request, auth, db).create_product(body)


@router.get(
    "/products",
    response_model=Page[ProductView],
    responses=error_responses(401, 403, 422),
)
def list_products(
    request: Request,
    auth: Auth,
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_archived: Annotated[bool, Query()] = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ProductView]:
    return _service(request, auth, db).list_products(
        page=page,
        page_size=page_size,
        include_archived=include_archived,
        query=q,
    )


@router.get(
    "/products/{product_id}",
    response_model=ProductView,
    responses=error_responses(401, 403, 404),
)
def read_product(product_id: UUID, request: Request, auth: Auth, db: Db) -> ProductView:
    return _service(request, auth, db).get_product(product_id)


@router.patch(
    "/products/{product_id}",
    response_model=ProductView,
    responses=error_responses(401, 403, 404, 409, 422),
)
def update_product(
    product_id: UUID,
    body: ProductUpdate,
    request: Request,
    auth: Auth,
    db: Db,
) -> ProductView:
    return _service(request, auth, db).update_product(product_id, body)


@router.post(
    "/products/{product_id}/archive",
    response_model=ProductView,
    responses=error_responses(401, 403, 404),
)
def archive_product(product_id: UUID, request: Request, auth: Auth, db: Db) -> ProductView:
    return _service(request, auth, db).archive_product(product_id)


@router.get(
    "/products/{product_id}/vendors",
    response_model=list[ProductVendorView],
    responses=error_responses(401, 403, 404),
)
def list_product_vendors(
    product_id: UUID,
    request: Request,
    auth: Auth,
    db: Db,
) -> list[ProductVendorView]:
    return _service(request, auth, db).list_product_vendors(product_id)


@router.put(
    "/products/{product_id}/vendors/{role}",
    response_model=ProductVendorView,
    responses=error_responses(401, 403, 404, 409, 422),
)
def assign_product_vendor(
    product_id: UUID,
    role: VendorRole,
    body: ProductVendorAssign,
    request: Request,
    auth: Auth,
    db: Db,
) -> ProductVendorView:
    return _service(request, auth, db).assign_product_vendor(product_id, role, body)


@router.delete(
    "/products/{product_id}/vendors/{role}",
    status_code=204,
    response_model=None,
    responses=error_responses(401, 403, 404),
)
def remove_product_vendor(
    product_id: UUID,
    role: VendorRole,
    request: Request,
    auth: Auth,
    db: Db,
) -> Response:
    _service(request, auth, db).remove_product_vendor(product_id, role)
    return Response(status_code=204)
