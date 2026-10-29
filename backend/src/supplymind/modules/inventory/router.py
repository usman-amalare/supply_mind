"""Stock ledger HTTP routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from supplymind.api.deps import Auth, Db, current_request_id, require_csrf
from supplymind.api.schemas import error_responses
from supplymind.core.pagination import Page
from supplymind.db.enums import StockReason
from supplymind.modules.inventory.schemas import (
    ProductStockSummary,
    StockAdjustmentCreate,
    StockAdjustmentView,
)
from supplymind.modules.inventory.service import InventoryService

router = APIRouter(dependencies=[Depends(require_csrf)])


def _service(request: Request, auth: Auth, db: Db) -> InventoryService:
    return InventoryService(
        db,
        auth.tenant,
        actor_id=auth.user_id,
        request_id=current_request_id(request),
    )


@router.post(
    "/products/{product_id}/stock-adjustments",
    status_code=201,
    response_model=StockAdjustmentView,
    responses=error_responses(401, 403, 404, 409, 422),
)
def create_stock_adjustment(
    product_id: UUID,
    body: StockAdjustmentCreate,
    request: Request,
    auth: Auth,
    db: Db,
) -> StockAdjustmentView:
    return _service(request, auth, db).create_adjustment(product_id, body)


@router.get(
    "/products/{product_id}/stock-adjustments",
    response_model=Page[StockAdjustmentView],
    responses=error_responses(401, 403, 404, 422),
)
def list_stock_adjustments(
    product_id: UUID,
    request: Request,
    auth: Auth,
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    reason: Annotated[StockReason | None, Query()] = None,
) -> Page[StockAdjustmentView]:
    return _service(request, auth, db).list_adjustments(
        product_id,
        page=page,
        page_size=page_size,
        reason=reason,
    )


@router.get(
    "/products/{product_id}/stock",
    response_model=ProductStockSummary,
    responses=error_responses(401, 403, 404),
)
def read_product_stock(
    product_id: UUID,
    request: Request,
    auth: Auth,
    db: Db,
) -> ProductStockSummary:
    return _service(request, auth, db).stock_summary(product_id)
