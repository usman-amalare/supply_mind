"""Tenant-scoped stock ledger. Append and read only; no update or delete methods."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import StockReason
from supplymind.db.repository import TenantRepository
from supplymind.modules.catalog.models import Product
from supplymind.modules.inventory.models import StockAdjustment


class InventoryRepository(TenantRepository):
    def __init__(self, session: Session, tenant: TenantContext) -> None:
        super().__init__(session, tenant)

    def get_product_for_update(self, product_id: UUID) -> Product | None:
        return self._session.scalar(
            select(Product)
            .where(Product.workspace_id == self.workspace_id, Product.id == product_id)
            .with_for_update()
        )

    def get_product(self, product_id: UUID) -> Product | None:
        return self._session.scalar(
            select(Product).where(
                Product.workspace_id == self.workspace_id,
                Product.id == product_id,
            )
        )

    def append(self, row: StockAdjustment) -> StockAdjustment:
        row.workspace_id = self.workspace_id
        self._session.add(row)
        return row

    def count_for_product(self, product_id: UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(StockAdjustment)
                .where(
                    StockAdjustment.workspace_id == self.workspace_id,
                    StockAdjustment.product_id == product_id,
                )
            )
            or 0
        )

    def latest_for_product(self, product_id: UUID) -> StockAdjustment | None:
        return self._session.scalar(
            select(StockAdjustment)
            .where(
                StockAdjustment.workspace_id == self.workspace_id,
                StockAdjustment.product_id == product_id,
            )
            .order_by(StockAdjustment.created_at.desc(), StockAdjustment.id.desc())
            .limit(1)
        )

    def list_for_product(
        self,
        product_id: UUID,
        *,
        page: int,
        page_size: int,
        reason: StockReason | None,
    ) -> tuple[list[StockAdjustment], int]:
        filters = [
            StockAdjustment.workspace_id == self.workspace_id,
            StockAdjustment.product_id == product_id,
        ]
        if reason is not None:
            filters.append(StockAdjustment.reason == reason)
        total = int(
            self._session.scalar(select(func.count()).select_from(StockAdjustment).where(*filters))
            or 0
        )
        statement = (
            select(StockAdjustment)
            .where(*filters)
            .order_by(StockAdjustment.created_at.desc(), StockAdjustment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self._session.scalars(statement)), total

    def set_product_stock(self, product: Product, balance: Decimal) -> None:
        product.current_stock = balance
