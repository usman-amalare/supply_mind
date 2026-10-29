"""Vendor, product, and primary/backup relationship rules."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplymind.clock import Clock
from supplymind.core.errors import AppError
from supplymind.core.ids import new_id
from supplymind.core.pagination import Page
from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import VendorRole
from supplymind.modules.audit.repository import AuditRepository
from supplymind.modules.catalog.models import Product, ProductVendor, Vendor
from supplymind.modules.catalog.repository import CatalogRepository
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
from supplymind.modules.catalog.values import money, optional_text, quantity, required_text
from supplymind.modules.identity.emails import normalize_email
from supplymind.modules.inventory.service import InventoryService
from supplymind.modules.workspaces.models import Workspace

_NOT_FOUND = AppError("not_found", "Resource not found.", status_code=404)
JsonObject = dict[str, object]


class CatalogService:
    def __init__(
        self,
        session: Session,
        tenant: TenantContext,
        clock: Clock,
        *,
        actor_id: UUID,
        request_id: str | None,
    ) -> None:
        self._session = session
        self._tenant = tenant
        self._clock = clock
        self._repo = CatalogRepository(session, tenant)
        self._audit = AuditRepository(session)
        self._actor_id = actor_id
        self._request_id = request_id

    def create_vendor(self, body: VendorCreate) -> VendorView:
        vendor = Vendor(
            id=new_id(),
            name=_text(body.name, 200, "name"),
            contact_name=_optional(body.contact_name, 200, "contact_name"),
            contact_email=_optional_email(body.contact_email),
            contact_phone=_optional(body.contact_phone, 40, "contact_phone"),
            typical_lead_time_days=body.typical_lead_time_days,
            imports_goods=body.imports_goods,
        )
        self._repo.add_vendor(vendor)
        self._audit_write(
            action="vendor_created",
            entity_type="vendor",
            entity_id=vendor.id,
            before=None,
            after=_vendor_audit(vendor),
        )
        self._session.commit()
        return _vendor_view(vendor)

    def get_vendor(self, vendor_id: UUID) -> VendorView:
        vendor = self._repo.get_vendor(vendor_id)
        if vendor is None:
            raise _NOT_FOUND
        return _vendor_view(vendor)

    def list_vendors(
        self,
        *,
        page: int,
        page_size: int,
        include_archived: bool,
        query: str | None,
    ) -> Page[VendorView]:
        items, total = self._repo.list_vendors(
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            query=_search(query),
        )
        return Page(
            items=[_vendor_view(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def update_vendor(self, vendor_id: UUID, body: VendorUpdate) -> VendorView:
        vendor = self._require_active_vendor(vendor_id)
        before = _vendor_audit(vendor)
        fields = body.model_fields_set
        if "name" in fields and body.name is not None:
            vendor.name = _text(body.name, 200, "name")
        if "contact_name" in fields:
            vendor.contact_name = _optional(body.contact_name, 200, "contact_name")
        if "contact_email" in fields:
            vendor.contact_email = _optional_email(body.contact_email)
        if "contact_phone" in fields:
            vendor.contact_phone = _optional(body.contact_phone, 40, "contact_phone")
        if "typical_lead_time_days" in fields and body.typical_lead_time_days is not None:
            vendor.typical_lead_time_days = body.typical_lead_time_days
        if "imports_goods" in fields and body.imports_goods is not None:
            vendor.imports_goods = body.imports_goods
        self._audit_write(
            action="vendor_updated",
            entity_type="vendor",
            entity_id=vendor.id,
            before=before,
            after=_vendor_audit(vendor),
        )
        self._session.commit()
        return _vendor_view(vendor)

    def archive_vendor(self, vendor_id: UUID) -> VendorView:
        vendor = self._repo.get_vendor(vendor_id)
        if vendor is None:
            raise _NOT_FOUND
        if vendor.archived_at is not None:
            return _vendor_view(vendor)
        if self._repo.count_active_product_links(vendor_id) > 0:
            raise AppError(
                "vendor_in_use",
                "Archive the linked products or reassign their vendors first.",
                status_code=409,
            )
        before = _vendor_audit(vendor)
        self._repo.archive_vendor(vendor, self._clock.now())
        self._audit_write(
            action="vendor_archived",
            entity_type="vendor",
            entity_id=vendor.id,
            before=before,
            after=_vendor_audit(vendor),
        )
        self._session.commit()
        return _vendor_view(vendor)

    def create_product(self, body: ProductCreate) -> ProductView:
        sku = _text(body.sku, 64, "sku")
        unit_cost, currency = self._cost_pair(body.unit_cost, body.unit_cost_currency)
        opening = _qty(body.current_stock, "current_stock")
        product = Product(
            id=new_id(),
            sku=sku,
            name=_text(body.name, 200, "name"),
            unit=_text(body.unit, 32, "unit"),
            current_stock=opening,
            reorder_threshold=_qty(body.reorder_threshold, "reorder_threshold"),
            unit_cost=unit_cost,
            unit_cost_currency=currency,
        )
        inventory = InventoryService(
            self._session,
            self._tenant,
            actor_id=self._actor_id,
            request_id=self._request_id,
        )
        try:
            self._repo.add_product(product)
            self._session.flush()
            inventory.initialize_opening(
                product,
                opening,
                actor_user_id=self._actor_id,
                note="Opening stock from product create",
                source_ref="product_create",
            )
            self._session.flush()
            self._audit_write(
                action="product_created",
                entity_type="product",
                entity_id=product.id,
                before=None,
                after=_product_audit(product),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if _is_sku_conflict(exc):
                raise AppError(
                    "sku_conflict",
                    "A product with that SKU already exists.",
                    status_code=409,
                ) from None
            raise AppError("internal_error", "Internal server error", status_code=500) from None
        except Exception:
            self._session.rollback()
            raise
        return _product_view(product)

    def get_product(self, product_id: UUID) -> ProductView:
        product = self._repo.get_product(product_id)
        if product is None:
            raise _NOT_FOUND
        return _product_view(product)

    def list_products(
        self,
        *,
        page: int,
        page_size: int,
        include_archived: bool,
        query: str | None,
    ) -> Page[ProductView]:
        items, total = self._repo.list_products(
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            query=_search(query),
        )
        return Page(
            items=[_product_view(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def update_product(self, product_id: UUID, body: ProductUpdate) -> ProductView:
        product = self._require_active_product(product_id)
        before = _product_audit(product)
        fields = body.model_fields_set
        if "sku" in fields and body.sku is not None:
            product.sku = _text(body.sku, 64, "sku")
        if "name" in fields and body.name is not None:
            product.name = _text(body.name, 200, "name")
        if "unit" in fields and body.unit is not None:
            product.unit = _text(body.unit, 32, "unit")
        if "reorder_threshold" in fields and body.reorder_threshold is not None:
            product.reorder_threshold = _qty(body.reorder_threshold, "reorder_threshold")
        if body.clear_unit_cost:
            product.unit_cost = None
            product.unit_cost_currency = None
        elif "unit_cost" in fields or "unit_cost_currency" in fields:
            cost = body.unit_cost if "unit_cost" in fields else product.unit_cost
            currency = (
                body.unit_cost_currency
                if "unit_cost_currency" in fields
                else product.unit_cost_currency
            )
            product.unit_cost, product.unit_cost_currency = self._cost_pair(cost, currency)
        try:
            self._session.flush()
            self._audit_write(
                action="product_updated",
                entity_type="product",
                entity_id=product.id,
                before=before,
                after=_product_audit(product),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if _is_sku_conflict(exc):
                raise AppError(
                    "sku_conflict",
                    "A product with that SKU already exists.",
                    status_code=409,
                ) from None
            raise AppError("internal_error", "Internal server error", status_code=500) from None
        return _product_view(product)

    def archive_product(self, product_id: UUID) -> ProductView:
        product = self._repo.get_product(product_id)
        if product is None:
            raise _NOT_FOUND
        if product.archived_at is not None:
            return _product_view(product)
        before = _product_audit(product)
        self._repo.archive_product(product, self._clock.now())
        self._audit_write(
            action="product_archived",
            entity_type="product",
            entity_id=product.id,
            before=before,
            after=_product_audit(product),
        )
        self._session.commit()
        return _product_view(product)

    def list_product_vendors(self, product_id: UUID) -> list[ProductVendorView]:
        if self._repo.get_product(product_id) is None:
            raise _NOT_FOUND
        rows = self._repo.list_links(product_id)
        return [
            ProductVendorView(
                id=link.id,
                product_id=link.product_id,
                vendor_id=link.vendor_id,
                role=link.role,
                vendor_name=vendor.name,
                vendor_archived_at=vendor.archived_at,
            )
            for link, vendor in rows
        ]

    def assign_product_vendor(
        self,
        product_id: UUID,
        role: VendorRole,
        body: ProductVendorAssign,
    ) -> ProductVendorView:
        product = self._require_active_product(product_id)
        vendor = self._require_active_vendor(body.vendor_id)
        existing_same = self._repo.get_link_for_vendor(product.id, vendor.id)
        existing_role = self._repo.get_link(product.id, role)
        before = _links_audit(self._repo.list_links(product.id))
        if existing_same is not None and existing_same.role == role:
            return self._link_view(existing_same, vendor)
        if existing_same is not None and existing_same.role != role:
            raise AppError(
                "vendor_role_conflict",
                "That vendor is already linked in the other role.",
                status_code=409,
            )
        try:
            if existing_role is not None:
                self._repo.delete_link(existing_role)
                self._session.flush()
            link = ProductVendor(
                id=new_id(),
                product_id=product.id,
                vendor_id=vendor.id,
                role=role,
            )
            self._repo.add_link(link)
            self._session.flush()
            self._audit_write(
                action="product_vendor_assigned",
                entity_type="product_vendor",
                entity_id=link.id,
                before=before,
                after=_links_audit(self._repo.list_links(product.id)),
            )
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise AppError(
                "product_vendor_conflict",
                "That product vendor assignment could not be saved.",
                status_code=409,
            ) from None
        return self._link_view(link, vendor)

    def remove_product_vendor(self, product_id: UUID, role: VendorRole) -> None:
        product = self._require_active_product(product_id)
        link = self._repo.get_link(product.id, role)
        if link is None:
            raise _NOT_FOUND
        before = _links_audit(self._repo.list_links(product.id))
        self._repo.delete_link(link)
        self._audit_write(
            action="product_vendor_removed",
            entity_type="product_vendor",
            entity_id=link.id,
            before=before,
            after=_links_audit(self._repo.list_links(product.id)),
        )
        self._session.commit()

    def _require_active_vendor(self, vendor_id: UUID) -> Vendor:
        vendor = self._repo.get_vendor(vendor_id)
        if vendor is None or vendor.archived_at is not None:
            raise _NOT_FOUND
        return vendor

    def _require_active_product(self, product_id: UUID) -> Product:
        product = self._repo.get_product(product_id)
        if product is None or product.archived_at is not None:
            raise _NOT_FOUND
        return product

    def _cost_pair(
        self,
        unit_cost: Decimal | None,
        currency: str | None,
    ) -> tuple[Decimal | None, str | None]:
        if unit_cost is None and currency is None:
            return None, None
        if unit_cost is None or currency is None:
            raise AppError(
                "validation_error",
                "Request validation failed",
                status_code=422,
                details={"field": "unit_cost"},
            )
        code = currency.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise AppError(
                "validation_error",
                "Request validation failed",
                status_code=422,
                details={"field": "unit_cost_currency"},
            )
        workspace = self._session.get(Workspace, self._tenant.workspace_id)
        if workspace is None:
            raise _NOT_FOUND
        try:
            return money(unit_cost), code
        except ValueError:
            raise AppError(
                "validation_error",
                "Request validation failed",
                status_code=422,
                details={"field": "unit_cost"},
            ) from None

    def _link_view(self, link: ProductVendor, vendor: Vendor) -> ProductVendorView:
        return ProductVendorView(
            id=link.id,
            product_id=link.product_id,
            vendor_id=link.vendor_id,
            role=link.role,
            vendor_name=vendor.name,
            vendor_archived_at=vendor.archived_at,
        )

    def _audit_write(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        before: JsonObject | None,
        after: JsonObject | None,
    ) -> None:
        self._audit.append(
            workspace_id=self._tenant.workspace_id,
            actor=str(self._actor_id),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            request_id=self._request_id,
        )


def _text(value: str, limit: int, field: str) -> str:
    try:
        return required_text(value, limit)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": field},
        ) from None


def _optional(value: str | None, limit: int, field: str) -> str | None:
    try:
        return optional_text(value, limit)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": field},
        ) from None


def _search(value: str | None) -> str | None:
    if value is None:
        return None
    return _optional(value, 100, "q")


def _qty(value: Decimal, field: str) -> Decimal:
    try:
        return quantity(value)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": field},
        ) from None


def _optional_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return normalize_email(cleaned)
    except ValueError:
        raise AppError(
            "validation_error",
            "Request validation failed",
            status_code=422,
            details={"field": "contact_email"},
        ) from None


def _vendor_view(vendor: Vendor) -> VendorView:
    return VendorView(
        id=vendor.id,
        name=vendor.name,
        contact_name=vendor.contact_name,
        contact_email=vendor.contact_email,
        contact_phone=vendor.contact_phone,
        typical_lead_time_days=vendor.typical_lead_time_days,
        imports_goods=vendor.imports_goods,
        archived_at=vendor.archived_at,
    )


def _product_view(product: Product) -> ProductView:
    return ProductView(
        id=product.id,
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        current_stock=product.current_stock,
        reorder_threshold=product.reorder_threshold,
        unit_cost=product.unit_cost,
        unit_cost_currency=product.unit_cost_currency,
        archived_at=product.archived_at,
    )


def _vendor_audit(vendor: Vendor) -> JsonObject:
    return {
        "name": vendor.name,
        "typical_lead_time_days": vendor.typical_lead_time_days,
        "imports_goods": vendor.imports_goods,
        "archived_at": vendor.archived_at.isoformat() if vendor.archived_at else None,
    }


def _product_audit(product: Product) -> JsonObject:
    return {
        "sku": product.sku,
        "name": product.name,
        "unit": product.unit,
        "current_stock": str(product.current_stock),
        "reorder_threshold": str(product.reorder_threshold),
        "unit_cost": str(product.unit_cost) if product.unit_cost is not None else None,
        "unit_cost_currency": product.unit_cost_currency,
        "archived_at": product.archived_at.isoformat() if product.archived_at else None,
    }


def _links_audit(rows: list[tuple[ProductVendor, Vendor]]) -> JsonObject:
    return {
        "links": [
            {"vendor_id": str(link.vendor_id), "role": link.role.value} for link, _vendor in rows
        ]
    }


def _is_sku_conflict(exc: IntegrityError) -> bool:
    orig = exc.orig
    diag = getattr(orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    if name == "uq_products_workspace_lower_sku":
        return True
    return "uq_products_workspace_lower_sku" in str(orig)
