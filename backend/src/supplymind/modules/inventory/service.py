"""Atomic stock adjustments and opening-balance initialization."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplymind.core.errors import AppError
from supplymind.core.ids import new_id
from supplymind.core.pagination import Page
from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import StockReason
from supplymind.modules.audit.repository import AuditRepository
from supplymind.modules.catalog.models import Product
from supplymind.modules.catalog.values import optional_text, quantity
from supplymind.modules.inventory.models import StockAdjustment
from supplymind.modules.inventory.repository import InventoryRepository
from supplymind.modules.inventory.schemas import (
    AdjustmentReason,
    LedgerStatus,
    ProductStockSummary,
    StockAdjustmentCreate,
    StockAdjustmentView,
)

_NOT_FOUND = AppError("not_found", "Resource not found.", status_code=404)


class InventoryService:
    def __init__(
        self,
        session: Session,
        tenant: TenantContext,
        *,
        actor_id: UUID,
        request_id: str | None,
    ) -> None:
        self._session = session
        self._tenant = tenant
        self._repo = InventoryRepository(session, tenant)
        self._audit = AuditRepository(session)
        self._actor_id = actor_id
        self._request_id = request_id

    def initialize_opening(
        self,
        product: Product,
        opening: Decimal,
        *,
        actor_user_id: UUID | None,
        note: str | None = None,
        source_ref: str | None = None,
    ) -> StockAdjustment:
        """Append the sole initial ledger row for a product. Caller owns the transaction."""
        balance = quantity(opening)
        if self._repo.count_for_product(product.id) > 0:
            raise AppError(
                "ledger_conflict",
                "This product already has a stock ledger.",
                status_code=409,
            )
        product.current_stock = balance
        row = StockAdjustment(
            id=new_id(),
            product_id=product.id,
            delta=balance,
            reason=StockReason.INITIAL,
            note=note,
            actor_user_id=actor_user_id,
            balance_after=balance,
            source_ref=source_ref,
        )
        self._repo.append(row)
        return row

    def create_adjustment(
        self,
        product_id: UUID,
        body: StockAdjustmentCreate,
    ) -> StockAdjustmentView:
        reason = StockReason(body.reason)
        delta = _signed_delta(body.delta, body.reason)
        note = _note(body.note)
        source_ref = _source_ref(body.source_ref)
        product = self._repo.get_product_for_update(product_id)
        if product is None or product.archived_at is not None:
            raise _NOT_FOUND
        if self._repo.count_for_product(product.id) == 0:
            raise AppError(
                "ledger_uninitialized",
                "This product has no stock ledger yet.",
                status_code=409,
            )
        previous = product.current_stock
        resulting = previous + delta
        if resulting < 0:
            raise AppError(
                "insufficient_stock",
                "The adjustment would leave stock below zero.",
                status_code=409,
                details={"current_stock": str(previous), "delta": str(delta)},
            )
        try:
            self._repo.set_product_stock(product, resulting)
            row = StockAdjustment(
                id=new_id(),
                product_id=product.id,
                delta=delta,
                reason=reason,
                note=note,
                actor_user_id=self._actor_id,
                balance_after=resulting,
                source_ref=source_ref,
            )
            self._repo.append(row)
            self._session.flush()
            self._audit.append(
                workspace_id=self._tenant.workspace_id,
                actor=str(self._actor_id),
                action="stock_adjusted",
                entity_type="stock_adjustment",
                entity_id=row.id,
                before={"current_stock": str(previous)},
                after={
                    "current_stock": str(resulting),
                    "delta": str(delta),
                    "reason": reason.value,
                    "source_ref": source_ref,
                },
                request_id=self._request_id,
            )
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise AppError(
                "ledger_conflict",
                "The stock adjustment could not be saved.",
                status_code=409,
            ) from None
        except Exception:
            self._session.rollback()
            raise
        return _view(row)

    def list_adjustments(
        self,
        product_id: UUID,
        *,
        page: int,
        page_size: int,
        reason: StockReason | None,
    ) -> Page[StockAdjustmentView]:
        if self._repo.get_product(product_id) is None:
            raise _NOT_FOUND
        items, total = self._repo.list_for_product(
            product_id,
            page=page,
            page_size=page_size,
            reason=reason,
        )
        return Page(
            items=[_view(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def stock_summary(self, product_id: UUID) -> ProductStockSummary:
        product = self._repo.get_product(product_id)
        if product is None:
            raise _NOT_FOUND
        latest = self._repo.latest_for_product(product_id)
        status: LedgerStatus
        if latest is None:
            status = "uninitialized"
            latest_balance = None
        elif latest.balance_after != product.current_stock:
            status = "mismatch"
            latest_balance = latest.balance_after
        else:
            status = "ok"
            latest_balance = latest.balance_after
        return ProductStockSummary(
            product_id=product.id,
            current_stock=product.current_stock,
            ledger_status=status,
            latest_balance_after=latest_balance,
        )


def _signed_delta(value: Decimal, reason: AdjustmentReason) -> Decimal:
    try:
        delta = _quantity_signed(value)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": "delta"},
        ) from None
    if delta == 0:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": "delta", "reason": "zero_not_allowed"},
        )
    if reason == "receipt" and delta <= 0:
        raise AppError(
            "invalid_adjustment",
            "A receipt must increase stock.",
            status_code=422,
            details={"field": "delta"},
        )
    if reason in {"sale_deduction", "damage"} and delta >= 0:
        raise AppError(
            "invalid_adjustment",
            "That reason must decrease stock.",
            status_code=422,
            details={"field": "delta"},
        )
    return delta


def _quantity_signed(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("invalid amount")
    # Signed deltas; magnitude uses the shared precision and upper bound.
    magnitude = quantity(abs(value))
    return -magnitude if value < 0 else magnitude


def _note(value: str | None) -> str | None:
    try:
        return optional_text(value, 2000)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": "note"},
        ) from None


def _source_ref(value: str | None) -> str | None:
    try:
        return optional_text(value, 200)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": "source_ref"},
        ) from None


def _view(row: StockAdjustment) -> StockAdjustmentView:
    return StockAdjustmentView(
        id=row.id,
        product_id=row.product_id,
        delta=row.delta,
        reason=row.reason,
        note=row.note,
        actor_user_id=row.actor_user_id,
        balance_after=row.balance_after,
        source_ref=row.source_ref,
        created_at=row.created_at,
    )
