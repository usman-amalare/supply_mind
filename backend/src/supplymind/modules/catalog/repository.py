"""Tenant-scoped catalog persistence. Every query filters by TenantContext."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import VendorRole
from supplymind.db.repository import TenantRepository
from supplymind.modules.catalog.models import Product, ProductVendor, Vendor


class CatalogRepository(TenantRepository):
    def __init__(self, session: Session, tenant: TenantContext) -> None:
        super().__init__(session, tenant)

    def add_vendor(self, vendor: Vendor) -> Vendor:
        vendor.workspace_id = self.workspace_id
        self._session.add(vendor)
        return vendor

    def get_vendor(self, vendor_id: UUID, *, include_archived: bool = True) -> Vendor | None:
        statement = select(Vendor).where(
            Vendor.workspace_id == self.workspace_id,
            Vendor.id == vendor_id,
        )
        if not include_archived:
            statement = statement.where(Vendor.archived_at.is_(None))
        return self._session.scalar(statement)

    def list_vendors(
        self,
        *,
        page: int,
        page_size: int,
        include_archived: bool,
        query: str | None,
    ) -> tuple[list[Vendor], int]:
        filters = [Vendor.workspace_id == self.workspace_id]
        if not include_archived:
            filters.append(Vendor.archived_at.is_(None))
        if query:
            pattern = f"%{query.casefold()}%"
            filters.append(
                or_(
                    func.lower(Vendor.name).like(pattern),
                    func.lower(func.coalesce(Vendor.contact_name, "")).like(pattern),
                )
            )
        total = int(
            self._session.scalar(select(func.count()).select_from(Vendor).where(*filters)) or 0
        )
        statement = (
            select(Vendor)
            .where(*filters)
            .order_by(Vendor.name.asc(), Vendor.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self._session.scalars(statement)), total

    def count_active_product_links(self, vendor_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(ProductVendor)
            .join(
                Product,
                (Product.workspace_id == ProductVendor.workspace_id)
                & (Product.id == ProductVendor.product_id),
            )
            .where(
                ProductVendor.workspace_id == self.workspace_id,
                ProductVendor.vendor_id == vendor_id,
                Product.archived_at.is_(None),
            )
        )
        return int(self._session.scalar(statement) or 0)

    def add_product(self, product: Product) -> Product:
        product.workspace_id = self.workspace_id
        self._session.add(product)
        return product

    def get_product(self, product_id: UUID, *, include_archived: bool = True) -> Product | None:
        statement = select(Product).where(
            Product.workspace_id == self.workspace_id,
            Product.id == product_id,
        )
        if not include_archived:
            statement = statement.where(Product.archived_at.is_(None))
        return self._session.scalar(statement)

    def get_product_by_lower_sku(self, sku: str) -> Product | None:
        return self._session.scalar(
            select(Product).where(
                Product.workspace_id == self.workspace_id,
                func.lower(Product.sku) == sku.casefold(),
            )
        )

    def list_products(
        self,
        *,
        page: int,
        page_size: int,
        include_archived: bool,
        query: str | None,
    ) -> tuple[list[Product], int]:
        filters = [Product.workspace_id == self.workspace_id]
        if not include_archived:
            filters.append(Product.archived_at.is_(None))
        if query:
            pattern = f"%{query.casefold()}%"
            filters.append(
                or_(
                    func.lower(Product.sku).like(pattern),
                    func.lower(Product.name).like(pattern),
                )
            )
        total = int(
            self._session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
        )
        statement = (
            select(Product)
            .where(*filters)
            .order_by(Product.sku.asc(), Product.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self._session.scalars(statement)), total

    def get_link(self, product_id: UUID, role: VendorRole) -> ProductVendor | None:
        return self._session.scalar(
            select(ProductVendor).where(
                ProductVendor.workspace_id == self.workspace_id,
                ProductVendor.product_id == product_id,
                ProductVendor.role == role,
            )
        )

    def get_link_for_vendor(self, product_id: UUID, vendor_id: UUID) -> ProductVendor | None:
        return self._session.scalar(
            select(ProductVendor).where(
                ProductVendor.workspace_id == self.workspace_id,
                ProductVendor.product_id == product_id,
                ProductVendor.vendor_id == vendor_id,
            )
        )

    def list_links(self, product_id: UUID) -> list[tuple[ProductVendor, Vendor]]:
        statement = (
            select(ProductVendor, Vendor)
            .join(
                Vendor,
                (Vendor.workspace_id == ProductVendor.workspace_id)
                & (Vendor.id == ProductVendor.vendor_id),
            )
            .where(
                ProductVendor.workspace_id == self.workspace_id,
                ProductVendor.product_id == product_id,
            )
            .order_by(ProductVendor.role.asc(), ProductVendor.id.asc())
        )
        return [(link, vendor) for link, vendor in self._session.execute(statement)]

    def add_link(self, link: ProductVendor) -> ProductVendor:
        link.workspace_id = self.workspace_id
        self._session.add(link)
        return link

    def delete_link(self, link: ProductVendor) -> None:
        self._session.delete(link)

    def archive_vendor(self, vendor: Vendor, when: datetime) -> None:
        vendor.archived_at = when

    def archive_product(self, product: Product, when: datetime) -> None:
        product.archived_at = when
