"""Vendor, product, relationship, and catalog isolation tests against PostgreSQL."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from supplymind.clock import FrozenClock
from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import VendorRole
from supplymind.db.session import make_engine, make_session_factory
from supplymind.modules.audit.models import AuditLog
from supplymind.modules.catalog.models import ProductVendor, Vendor
from supplymind.modules.catalog.repository import CatalogRepository
from supplymind.modules.catalog.schemas import ProductVendorAssign
from supplymind.modules.catalog.service import CatalogService
from tests.integration.test_identity import (
    _START,
    _as,
    _csrf,
    _register,
    db_session,
    make_client,
)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(_START)


@pytest.fixture
def client(database_url: str, clock: FrozenClock) -> Iterator[TestClient]:
    with make_client(database_url, clock) as (api, _clock):
        yield api


def _auth(client: TestClient, name: str = "Acme Stores") -> dict[str, object]:
    body, cookie = _register(client, name=name)
    _as(client, cookie)
    return body


def _headers(body: dict[str, object]) -> dict[str, str]:
    return {"X-CSRF-Token": _csrf(body)}


def _create_vendor(
    client: TestClient,
    auth: dict[str, object],
    *,
    name: str = "Lagos Supplies",
    lead: int = 7,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/vendors",
        headers=_headers(auth),
        json={
            "name": name,
            "contact_name": "Ada",
            "contact_email": "Ada@Example.com",
            "contact_phone": "+2348012345678",
            "typical_lead_time_days": lead,
            "imports_goods": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_product(
    client: TestClient,
    auth: dict[str, object],
    *,
    sku: str = "SKU-1",
    name: str = "Rice 50kg",
    stock: str = "0",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/products",
        headers=_headers(auth),
        json={
            "sku": sku,
            "name": name,
            "unit": "bag",
            "reorder_threshold": "5",
            "current_stock": stock,
            "unit_cost": "12000.50",
            "unit_cost_currency": "NGN",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_vendor_crud_list_archive_and_validation(client: TestClient, database_url: str) -> None:
    auth = _auth(client)
    created = _create_vendor(client, auth)
    assert created["contact_email"] == "ada@example.com"
    assert created["imports_goods"] is True
    assert created["archived_at"] is None
    vendor_id = created["id"]
    listed = client.get("/api/v1/vendors")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == vendor_id
    got = client.get(f"/api/v1/vendors/{vendor_id}")
    assert got.status_code == 200
    assert got.json()["name"] == "Lagos Supplies"
    updated = client.patch(
        f"/api/v1/vendors/{vendor_id}",
        headers=_headers(auth),
        json={"typical_lead_time_days": 10, "name": " Lagos Supplies Ltd "},
    )
    assert updated.status_code == 200
    assert updated.json()["typical_lead_time_days"] == 10
    assert updated.json()["name"] == "Lagos Supplies Ltd"
    negative = client.post(
        "/api/v1/vendors",
        headers=_headers(auth),
        json={"name": "Bad", "typical_lead_time_days": -1},
    )
    assert negative.status_code == 422
    workspace = client.post(
        "/api/v1/vendors",
        headers=_headers(auth),
        json={"name": "Spy", "typical_lead_time_days": 1, "workspace_id": str(uuid4())},
    )
    assert workspace.status_code == 422
    archived = client.post(f"/api/v1/vendors/{vendor_id}/archive", headers=_headers(auth))
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    again = client.post(f"/api/v1/vendors/{vendor_id}/archive", headers=_headers(auth))
    assert again.status_code == 200
    assert again.json()["archived_at"] == archived.json()["archived_at"]
    active = client.get("/api/v1/vendors")
    assert active.json()["total"] == 0
    with_archived = client.get("/api/v1/vendors", params={"include_archived": True})
    assert with_archived.json()["total"] == 1
    detail = client.get(f"/api/v1/vendors/{vendor_id}")
    assert detail.status_code == 200
    assert detail.json()["archived_at"] is not None
    with db_session(database_url) as session:
        row = session.get(Vendor, UUID(str(vendor_id)))
        assert row is not None
        assert row.archived_at is not None
        audits = list(session.scalars(select(AuditLog).where(AuditLog.action == "vendor_archived")))
        assert audits


def test_vendor_archive_blocked_while_linked_to_active_product(client: TestClient) -> None:
    auth = _auth(client)
    vendor = _create_vendor(client, auth)
    product = _create_product(client, auth)
    assigned = client.put(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(auth),
        json={"vendor_id": vendor["id"]},
    )
    assert assigned.status_code == 200
    blocked = client.post(f"/api/v1/vendors/{vendor['id']}/archive", headers=_headers(auth))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "vendor_in_use"
    client.post(f"/api/v1/products/{product['id']}/archive", headers=_headers(auth))
    freed = client.post(f"/api/v1/vendors/{vendor['id']}/archive", headers=_headers(auth))
    assert freed.status_code == 200
    assert freed.json()["archived_at"] is not None
    links = client.get(f"/api/v1/products/{product['id']}/vendors")
    assert links.status_code == 200
    assert links.json()[0]["vendor_id"] == vendor["id"]


def test_product_crud_sku_rules_and_stock_protection(client: TestClient) -> None:
    auth = _auth(client)
    created = _create_product(client, auth, sku="AbC-1", stock="12.500")
    assert created["sku"] == "AbC-1"
    assert Decimal(created["current_stock"]) == Decimal("12.500")
    assert created["unit_cost_currency"] == "NGN"
    duplicate = client.post(
        "/api/v1/products",
        headers=_headers(auth),
        json={
            "sku": "abc-1",
            "name": "Other",
            "unit": "bag",
            "reorder_threshold": "1",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "sku_conflict"
    negative = client.post(
        "/api/v1/products",
        headers=_headers(auth),
        json={
            "sku": "NEG",
            "name": "Bad",
            "unit": "bag",
            "reorder_threshold": "-1",
        },
    )
    assert negative.status_code == 422
    stock_update = client.patch(
        f"/api/v1/products/{created['id']}",
        headers=_headers(auth),
        json={"current_stock": "99"},
    )
    assert stock_update.status_code == 422
    updated = client.patch(
        f"/api/v1/products/{created['id']}",
        headers=_headers(auth),
        json={"name": "Rice 25kg", "reorder_threshold": "8.000"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Rice 25kg"
    assert Decimal(updated.json()["current_stock"]) == Decimal("12.500")
    cleared = client.patch(
        f"/api/v1/products/{created['id']}",
        headers=_headers(auth),
        json={"clear_unit_cost": True},
    )
    assert cleared.status_code == 200
    assert cleared.json()["unit_cost"] is None
    assert cleared.json()["unit_cost_currency"] is None
    archived = client.post(
        f"/api/v1/products/{created['id']}/archive",
        headers=_headers(auth),
    )
    assert archived.status_code == 200
    listed = client.get("/api/v1/products")
    assert listed.json()["total"] == 0
    with_archived = client.get("/api/v1/products", params={"include_archived": True})
    assert with_archived.json()["total"] == 1
    assert client.get(f"/api/v1/products/{created['id']}").status_code == 200


def test_same_sku_allowed_in_different_workspaces(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    _create_product(client, first, sku="SHARED")
    second = _auth(client, name="Beta")
    other = _create_product(client, second, sku="shared")
    assert other["sku"] == "shared"


def test_product_vendor_primary_backup_replace_and_remove(client: TestClient) -> None:
    auth = _auth(client)
    primary = _create_vendor(client, auth, name="Primary Co")
    backup = _create_vendor(client, auth, name="Backup Co")
    replacement = _create_vendor(client, auth, name="Replacement Co")
    product = _create_product(client, auth)
    first = client.put(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(auth),
        json={"vendor_id": primary["id"]},
    )
    assert first.status_code == 200
    assert first.json()["role"] == "primary"
    second_primary = client.put(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(auth),
        json={"vendor_id": primary["id"]},
    )
    assert second_primary.status_code == 200
    assert second_primary.json()["id"] == first.json()["id"]
    as_backup = client.put(
        f"/api/v1/products/{product['id']}/vendors/backup",
        headers=_headers(auth),
        json={"vendor_id": primary["id"]},
    )
    assert as_backup.status_code == 409
    assert as_backup.json()["error"]["code"] == "vendor_role_conflict"
    backup_link = client.put(
        f"/api/v1/products/{product['id']}/vendors/backup",
        headers=_headers(auth),
        json={"vendor_id": backup["id"]},
    )
    assert backup_link.status_code == 200
    replaced = client.put(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(auth),
        json={"vendor_id": replacement["id"]},
    )
    assert replaced.status_code == 200
    assert replaced.json()["vendor_id"] == replacement["id"]
    links = client.get(f"/api/v1/products/{product['id']}/vendors")
    assert links.status_code == 200
    roles = {item["role"]: item["vendor_id"] for item in links.json()}
    assert roles == {"primary": replacement["id"], "backup": backup["id"]}
    removed = client.delete(
        f"/api/v1/products/{product['id']}/vendors/backup",
        headers=_headers(auth),
    )
    assert removed.status_code == 204
    remaining = client.get(f"/api/v1/products/{product['id']}/vendors")
    assert len(remaining.json()) == 1
    assert remaining.json()[0]["role"] == "primary"
    missing = client.delete(
        f"/api/v1/products/{product['id']}/vendors/backup",
        headers=_headers(auth),
    )
    assert missing.status_code == 404


def test_product_vendor_rejects_missing_and_archived_targets(client: TestClient) -> None:
    auth = _auth(client)
    product = _create_product(client, auth)
    missing = client.put(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(auth),
        json={"vendor_id": str(uuid4())},
    )
    assert missing.status_code == 404
    vendor = _create_vendor(client, auth)
    client.post(f"/api/v1/vendors/{vendor['id']}/archive", headers=_headers(auth))
    archived = client.put(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(auth),
        json={"vendor_id": vendor["id"]},
    )
    assert archived.status_code == 404
    ghost_product = client.put(
        f"/api/v1/products/{uuid4()}/vendors/primary",
        headers=_headers(auth),
        json={"vendor_id": vendor["id"]},
    )
    assert ghost_product.status_code == 404


def test_pagination_is_stable(client: TestClient) -> None:
    auth = _auth(client)
    for index in range(3):
        _create_vendor(client, auth, name=f"Vendor {index}")
        _create_product(client, auth, sku=f"P-{index}", name=f"Product {index}")
    page1 = client.get("/api/v1/vendors", params={"page": 1, "page_size": 2})
    page2 = client.get("/api/v1/vendors", params={"page": 2, "page_size": 2})
    assert page1.json()["total"] == 3
    assert len(page1.json()["items"]) == 2
    assert len(page2.json()["items"]) == 1
    ids = [item["id"] for item in page1.json()["items"] + page2.json()["items"]]
    assert len(set(ids)) == 3
    products = client.get("/api/v1/products", params={"page": 1, "page_size": 2})
    assert products.json()["total"] == 3
    assert len(products.json()["items"]) == 2


def test_unauthenticated_catalog_access_is_rejected(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/v1/vendors").status_code == 401
    assert client.get("/api/v1/products").status_code == 401
    assert client.post(
        "/api/v1/vendors", json={"name": "X", "typical_lead_time_days": 1}
    ).status_code in {
        401,
        403,
    }


def test_vendors_list_cannot_see_other_workspace(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    vendor = _create_vendor(client, first, name="Secret Vendor")
    second = _auth(client, name="Beta")
    listed = client.get("/api/v1/vendors")
    assert listed.json()["total"] == 0
    assert client.get(f"/api/v1/vendors/{vendor['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/vendors/{vendor['id']}",
            headers=_headers(second),
            json={"name": "Hijack"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/vendors/{vendor['id']}/archive",
            headers=_headers(second),
        ).status_code
        == 404
    )


def test_products_list_cannot_see_other_workspace(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    product = _create_product(client, first, sku="ALPHA")
    second = _auth(client, name="Beta")
    listed = client.get("/api/v1/products")
    assert listed.json()["total"] == 0
    assert client.get(f"/api/v1/products/{product['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/products/{product['id']}",
            headers=_headers(second),
            json={"name": "Hijack"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/products/{product['id']}/archive",
            headers=_headers(second),
        ).status_code
        == 404
    )


def test_cannot_link_foreign_vendor_or_product(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    foreign_vendor = _create_vendor(client, first, name="Foreign Vendor")
    foreign_product = _create_product(client, first, sku="FOREIGN")
    second = _auth(client, name="Beta")
    local_product = _create_product(client, second, sku="LOCAL")
    local_vendor = _create_vendor(client, second, name="Local Vendor")
    cross = client.put(
        f"/api/v1/products/{local_product['id']}/vendors/primary",
        headers=_headers(second),
        json={"vendor_id": foreign_vendor["id"]},
    )
    assert cross.status_code == 404
    other = client.put(
        f"/api/v1/products/{foreign_product['id']}/vendors/primary",
        headers=_headers(second),
        json={"vendor_id": local_vendor["id"]},
    )
    assert other.status_code == 404
    assert client.get(f"/api/v1/products/{foreign_product['id']}/vendors").status_code == 404
    assert (
        client.delete(
            f"/api/v1/products/{foreign_product['id']}/vendors/primary",
            headers=_headers(second),
        ).status_code
        == 404
    )


def test_catalog_body_cannot_switch_tenant(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    vendor = _create_vendor(client, first)
    product = _create_product(client, first)
    foreign = str(uuid4())
    assert (
        client.patch(
            f"/api/v1/vendors/{vendor['id']}",
            headers=_headers(first),
            json={"name": "Still Mine", "workspace_id": foreign},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/products/{product['id']}",
            headers=_headers(first),
            json={"name": "Still Mine", "workspace_id": foreign},
        ).status_code
        == 422
    )
    listed = client.get("/api/v1/vendors", params={"workspace_id": foreign})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_catalog_create_rejects_foreign_workspace_id(client: TestClient) -> None:
    auth = _auth(client)
    assert (
        client.post(
            "/api/v1/vendors",
            headers=_headers(auth),
            json={
                "name": "Nope",
                "typical_lead_time_days": 1,
                "workspace_id": str(uuid4()),
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/products",
            headers=_headers(auth),
            json={
                "sku": "X",
                "name": "Nope",
                "unit": "ea",
                "reorder_threshold": "1",
                "workspace_id": str(uuid4()),
            },
        ).status_code
        == 422
    )


def test_product_vendors_assign_isolation(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    foreign_vendor = _create_vendor(client, first)
    second = _auth(client, name="Beta")
    product = _create_product(client, second)
    response = client.put(
        f"/api/v1/products/{product['id']}/vendors/backup",
        headers=_headers(second),
        json={"vendor_id": foreign_vendor["id"]},
    )
    assert response.status_code == 404


def test_product_vendors_remove_isolation(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    vendor = _create_vendor(client, first)
    product = _create_product(client, first)
    client.put(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(first),
        json={"vendor_id": vendor["id"]},
    )
    second = _auth(client, name="Beta")
    response = client.delete(
        f"/api/v1/products/{product['id']}/vendors/primary",
        headers=_headers(second),
    )
    assert response.status_code == 404


def test_database_rejects_cross_workspace_product_vendor(
    client: TestClient,
    database_url: str,
) -> None:
    first = _auth(client, name="Alpha")
    vendor = _create_vendor(client, first)
    second = _auth(client, name="Beta")
    product = _create_product(client, second)
    second_workspace = UUID(str(second["workspace"]["id"]))  # type: ignore[index]
    with db_session(database_url) as session:
        session.add(
            ProductVendor(
                workspace_id=second_workspace,
                product_id=UUID(str(product["id"])),
                vendor_id=UUID(str(vendor["id"])),
                role=VendorRole.PRIMARY,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_concurrent_primary_vendor_assignment(database_url: str, clock: FrozenClock) -> None:
    with make_client(database_url, clock) as (client, _clock):
        auth = _auth(client)
        product = _create_product(client, auth)
        vendors = [_create_vendor(client, auth, name=f"Race {index}") for index in range(2)]
        workspace_id = UUID(str(auth["workspace"]["id"]))  # type: ignore[index]
        product_id = UUID(str(product["id"]))
        engine = make_engine(database_url)
        factory = make_session_factory(engine)
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        lock = threading.Lock()

        def attempt(vendor_id: UUID) -> None:
            session = factory()
            service = CatalogService(
                session,
                TenantContext(workspace_id),
                clock,
                actor_id=UUID(str(auth["user"]["id"])),  # type: ignore[index]
                request_id="race",
            )
            try:
                barrier.wait(timeout=10)
                try:
                    service.assign_product_vendor(
                        product_id,
                        VendorRole.PRIMARY,
                        ProductVendorAssign(vendor_id=vendor_id),
                    )
                    result = "ok"
                except Exception as exc:
                    result = getattr(exc, "code", type(exc).__name__)
            finally:
                session.close()
            with lock:
                outcomes.append(str(result))

        threads = [
            threading.Thread(target=attempt, args=(UUID(str(vendors[0]["id"])),)),
            threading.Thread(target=attempt, args=(UUID(str(vendors[1]["id"])),)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        engine.dispose()
        assert outcomes.count("ok") == 1
        assert any(code in {"product_vendor_conflict", "ok"} for code in outcomes)
        with db_session(database_url) as session:
            links = list(
                session.scalars(
                    select(ProductVendor).where(
                        ProductVendor.product_id == product_id,
                        ProductVendor.role == VendorRole.PRIMARY,
                    )
                )
            )
            assert len(links) == 1


def test_repository_requires_tenant_context(database_url: str) -> None:
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        with pytest.raises(TypeError):
            CatalogRepository(session, None)  # type: ignore[arg-type]
    finally:
        session.close()
        engine.dispose()
