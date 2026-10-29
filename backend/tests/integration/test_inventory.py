"""Stock ledger, concurrency, and append-only tests against PostgreSQL."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError, IntegrityError

from supplymind.clock import FrozenClock
from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import StockReason
from supplymind.db.session import make_engine, make_session_factory
from supplymind.modules.audit.models import AuditLog
from supplymind.modules.catalog.models import Product
from supplymind.modules.inventory.models import StockAdjustment
from supplymind.modules.inventory.repository import InventoryRepository
from supplymind.modules.inventory.schemas import StockAdjustmentCreate
from supplymind.modules.inventory.service import InventoryService
from tests.integration.database import downgrade, migrate
from tests.integration.test_catalog import _auth, _create_product, _headers
from tests.integration.test_identity import _START, db_session, make_client


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(_START)


@pytest.fixture
def client(database_url: str, clock: FrozenClock) -> Iterator[TestClient]:
    with make_client(database_url, clock) as (api, _clock):
        yield api


def _adjust(
    client: TestClient,
    auth: dict[str, object],
    product_id: object,
    *,
    delta: str,
    reason: str,
    note: str | None = None,
) -> object:
    body: dict[str, object] = {"delta": delta, "reason": reason}
    if note is not None:
        body["note"] = note
    return client.post(
        f"/api/v1/products/{product_id}/stock-adjustments",
        headers=_headers(auth),
        json=body,
    )


def test_product_create_writes_initial_ledger_entry(
    client: TestClient,
    database_url: str,
) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="12.500")
    history = client.get(f"/api/v1/products/{product['id']}/stock-adjustments")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    row = history.json()["items"][0]
    assert row["reason"] == "initial"
    assert Decimal(row["delta"]) == Decimal("12.500")
    assert Decimal(row["balance_after"]) == Decimal("12.500")
    assert row["source_ref"] == "product_create"
    summary = client.get(f"/api/v1/products/{product['id']}/stock")
    assert summary.status_code == 200
    assert summary.json()["ledger_status"] == "ok"
    assert Decimal(summary.json()["current_stock"]) == Decimal("12.500")
    zero = _create_product(client, auth, sku="ZERO-1", stock="0")
    zero_history = client.get(f"/api/v1/products/{zero['id']}/stock-adjustments")
    assert zero_history.json()["total"] == 1
    assert Decimal(zero_history.json()["items"][0]["delta"]) == Decimal("0")
    with db_session(database_url) as session:
        count = session.scalar(
            select(StockAdjustment).where(
                StockAdjustment.product_id == UUID(str(product["id"])),
                StockAdjustment.reason == StockReason.INITIAL,
            )
        )
        assert count is not None


def test_product_create_rolls_back_when_opening_ledger_fails(
    client: TestClient,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _auth(client)
    workspace_id = UUID(str(auth["workspace"]["id"]))  # type: ignore[index]

    def boom(self: InventoryService, *args: object, **kwargs: object) -> object:
        raise RuntimeError("forced-ledger-failure")

    monkeypatch.setattr(InventoryService, "initialize_opening", boom)
    with pytest.raises(RuntimeError, match="forced-ledger-failure"):
        client.post(
            "/api/v1/products",
            headers=_headers(auth),
            json={
                "sku": f"FAIL-{uuid4().hex[:8]}",
                "name": "Broken",
                "unit": "ea",
                "reorder_threshold": "1",
                "current_stock": "5",
            },
        )
    with db_session(database_url) as session:
        leftover = list(
            session.scalars(select(Product).where(Product.workspace_id == workspace_id))
        )
        assert leftover == []
        adjustments = list(
            session.scalars(
                select(StockAdjustment).where(StockAdjustment.workspace_id == workspace_id)
            )
        )
        assert adjustments == []


def test_adjustment_reasons_and_insufficient_stock(client: TestClient) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="10")
    receipt = _adjust(client, auth, product["id"], delta="5", reason="receipt")
    assert receipt.status_code == 201
    assert Decimal(receipt.json()["balance_after"]) == Decimal("15")
    sale = _adjust(client, auth, product["id"], delta="-4", reason="sale_deduction")
    assert sale.status_code == 201
    assert Decimal(sale.json()["balance_after"]) == Decimal("11")
    damage = _adjust(client, auth, product["id"], delta="-1", reason="damage")
    assert damage.status_code == 201
    correction_up = _adjust(client, auth, product["id"], delta="2", reason="correction")
    assert correction_up.status_code == 201
    manual = _adjust(client, auth, product["id"], delta="-3", reason="manual_count")
    assert manual.status_code == 201
    assert Decimal(manual.json()["balance_after"]) == Decimal("9")
    bad_receipt = _adjust(client, auth, product["id"], delta="-1", reason="receipt")
    assert bad_receipt.status_code == 422
    bad_sale = _adjust(client, auth, product["id"], delta="1", reason="sale_deduction")
    assert bad_sale.status_code == 422
    initial = _adjust(client, auth, product["id"], delta="1", reason="initial")
    assert initial.status_code == 422
    zero = _adjust(client, auth, product["id"], delta="0", reason="correction")
    assert zero.status_code == 422
    overdraw = _adjust(client, auth, product["id"], delta="-100", reason="sale_deduction")
    assert overdraw.status_code == 409
    assert overdraw.json()["error"]["code"] == "insufficient_stock"
    product_body = client.get(f"/api/v1/products/{product['id']}")
    assert Decimal(product_body.json()["current_stock"]) == Decimal("9")
    stock_patch = client.patch(
        f"/api/v1/products/{product['id']}",
        headers=_headers(auth),
        json={"current_stock": "1"},
    )
    assert stock_patch.status_code == 422


def test_list_adjustments_order_filter_and_pagination(client: TestClient) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="0")
    for delta in ("1", "2", "3"):
        created = _adjust(client, auth, product["id"], delta=delta, reason="receipt")
        assert created.status_code == 201
    page1 = client.get(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        params={"page": 1, "page_size": 2},
    )
    assert page1.status_code == 200
    assert page1.json()["total"] == 4
    assert len(page1.json()["items"]) == 2
    deltas = [Decimal(item["delta"]) for item in page1.json()["items"]]
    assert deltas[0] >= deltas[1]
    receipts = client.get(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        params={"reason": "receipt"},
    )
    assert receipts.json()["total"] == 3
    assert all(item["reason"] == "receipt" for item in receipts.json()["items"])


def test_archived_product_cannot_be_adjusted(client: TestClient) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="5")
    client.post(f"/api/v1/products/{product['id']}/archive", headers=_headers(auth))
    response = _adjust(client, auth, product["id"], delta="1", reason="receipt")
    assert response.status_code == 404


def test_stock_routes_are_isolated(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    product = _create_product(client, first, sku="ALPHA-STOCK", stock="8")
    second = _auth(client, name="Beta")
    assert client.get(f"/api/v1/products/{product['id']}/stock-adjustments").status_code == 404
    assert client.get(f"/api/v1/products/{product['id']}/stock").status_code == 404
    assert _adjust(client, second, product["id"], delta="1", reason="receipt").status_code == 404


def test_stock_create_rejects_client_controlled_fields(client: TestClient) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="1")
    response = client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        headers=_headers(auth),
        json={
            "delta": "1",
            "reason": "receipt",
            "workspace_id": str(uuid4()),
            "balance_after": "99",
            "actor_user_id": str(uuid4()),
        },
    )
    assert response.status_code == 422


def test_stock_list_query_cannot_switch_tenant(client: TestClient) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="1")
    response = client.get(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        params={"workspace_id": str(uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_stock_summary_isolation(client: TestClient) -> None:
    first = _auth(client, name="Alpha")
    product = _create_product(client, first, stock="2")
    _auth(client, name="Beta")
    assert client.get(f"/api/v1/products/{product['id']}/stock").status_code == 404


def test_unauthenticated_stock_routes_fail(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get(f"/api/v1/products/{uuid4()}/stock-adjustments").status_code == 401
    assert client.get(f"/api/v1/products/{uuid4()}/stock").status_code == 401
    assert client.post(
        f"/api/v1/products/{uuid4()}/stock-adjustments",
        json={"delta": "1", "reason": "receipt"},
    ).status_code in {401, 403}


def test_csrf_required_for_stock_adjustment(client: TestClient) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="1")
    missing = client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        json={"delta": "1", "reason": "receipt"},
    )
    assert missing.status_code == 403


def test_concurrent_insufficient_stock_allows_one_winner(
    database_url: str,
    clock: FrozenClock,
) -> None:
    with make_client(database_url, clock) as (client, _clock):
        auth = _auth(client)
        product = _create_product(client, auth, stock="10")
        workspace_id = UUID(str(auth["workspace"]["id"]))  # type: ignore[index]
        product_id = UUID(str(product["id"]))
        actor_id = UUID(str(auth["user"]["id"]))  # type: ignore[index]
        engine = make_engine(database_url)
        factory = make_session_factory(engine)
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        lock = threading.Lock()

        def attempt() -> None:
            session = factory()
            service = InventoryService(
                session,
                TenantContext(workspace_id),
                actor_id=actor_id,
                request_id="race",
            )
            try:
                barrier.wait(timeout=10)
                try:
                    service.create_adjustment(
                        product_id,
                        StockAdjustmentCreate(delta=Decimal("-7"), reason="sale_deduction"),
                    )
                    result = "ok"
                except Exception as exc:
                    result = getattr(exc, "code", type(exc).__name__)
            finally:
                session.close()
            with lock:
                outcomes.append(str(result))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        engine.dispose()
        assert outcomes.count("ok") == 1
        assert "insufficient_stock" in outcomes
        with db_session(database_url) as session:
            stored = session.get(Product, product_id)
            assert stored is not None
            assert stored.current_stock == Decimal("3")
            rows = list(
                session.scalars(
                    select(StockAdjustment).where(
                        StockAdjustment.product_id == product_id,
                        StockAdjustment.reason == StockReason.SALE_DEDUCTION,
                    )
                )
            )
            assert len(rows) == 1
            assert rows[0].balance_after == Decimal("3")


def test_append_only_update_and_delete_remain_rejected(
    client: TestClient,
    database_url: str,
) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="4")
    created = _adjust(client, auth, product["id"], delta="1", reason="receipt")
    assert created.status_code == 201
    adjustment_id = UUID(str(created.json()["id"]))
    with db_session(database_url) as session:
        with pytest.raises(DatabaseError, match="append-only"):
            session.execute(
                text("UPDATE stock_adjustments SET note = 'x' WHERE id = :id"),
                {"id": adjustment_id},
            )
        session.rollback()
        with pytest.raises(DatabaseError, match="append-only"):
            session.execute(
                text("DELETE FROM stock_adjustments WHERE id = :id"),
                {"id": adjustment_id},
            )
        session.rollback()
    correction = _adjust(client, auth, product["id"], delta="-1", reason="correction")
    assert correction.status_code == 201
    history = client.get(f"/api/v1/products/{product['id']}/stock-adjustments")
    assert history.json()["total"] == 3


def test_duplicate_initial_is_rejected_by_database(
    client: TestClient,
    database_url: str,
) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="2")
    with db_session(database_url) as session:
        session.add(
            StockAdjustment(
                workspace_id=UUID(str(auth["workspace"]["id"])),  # type: ignore[index]
                product_id=UUID(str(product["id"])),
                delta=Decimal("2"),
                reason=StockReason.INITIAL,
                balance_after=Decimal("2"),
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_migration_backfill_and_downgrade(database_url: str) -> None:
    downgrade(database_url, "0001_initial_schema")
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        from supplymind.core.ids import new_id
        from supplymind.modules.workspaces.models import Workspace

        workspace = Workspace(id=new_id(), name="Legacy", timezone="Africa/Lagos", currency="NGN")
        session.add(workspace)
        session.flush()
        product = Product(
            id=new_id(),
            workspace_id=workspace.id,
            sku="LEGACY-1",
            name="Legacy",
            unit="ea",
            current_stock=Decimal("7.000"),
            reorder_threshold=Decimal("1"),
        )
        session.add(product)
        session.commit()
        product_id = product.id
        workspace_id = workspace.id
    finally:
        session.close()
        engine.dispose()

    migrate(database_url, "head")
    with db_session(database_url) as session:
        rows = list(
            session.scalars(select(StockAdjustment).where(StockAdjustment.product_id == product_id))
        )
        assert len(rows) == 1
        assert rows[0].reason == StockReason.INITIAL
        assert rows[0].source_ref == "stage4_backfill"
        assert rows[0].balance_after == Decimal("7.000")
        stored = session.get(Product, product_id)
        assert stored is not None
        assert stored.current_stock == Decimal("7.000")

    downgrade(database_url, "0001_initial_schema")
    with db_session(database_url) as session:
        # Downgrade keeps baseline rows; only drops Stage 4 constraints/index.
        rows = list(
            session.scalars(select(StockAdjustment).where(StockAdjustment.product_id == product_id))
        )
        assert len(rows) == 1
        stored = session.get(Product, product_id)
        assert stored is not None
        assert stored.workspace_id == workspace_id

    migrate(database_url, "head")
    with db_session(database_url) as session:
        rows = list(
            session.scalars(
                select(StockAdjustment).where(
                    StockAdjustment.product_id == product_id,
                    StockAdjustment.reason == StockReason.INITIAL,
                )
            )
        )
        assert len(rows) == 1


def test_mismatch_is_detected_without_auto_repair(
    client: TestClient,
    database_url: str,
) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="5")
    with db_session(database_url) as session:
        stored = session.get(Product, UUID(str(product["id"])))
        assert stored is not None
        stored.current_stock = Decimal("99")
        session.commit()
    summary = client.get(f"/api/v1/products/{product['id']}/stock")
    assert summary.status_code == 200
    assert summary.json()["ledger_status"] == "mismatch"
    assert Decimal(summary.json()["current_stock"]) == Decimal("99")
    assert Decimal(summary.json()["latest_balance_after"]) == Decimal("5")
    product_again = client.get(f"/api/v1/products/{product['id']}")
    assert Decimal(product_again.json()["current_stock"]) == Decimal("99")


def test_repository_has_no_update_delete_and_requires_tenant(database_url: str) -> None:
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        with pytest.raises(TypeError):
            InventoryRepository(session, None)  # type: ignore[arg-type]
        assert not hasattr(InventoryRepository, "update")
        assert not hasattr(InventoryRepository, "delete")
    finally:
        session.close()
        engine.dispose()


def test_adjustment_writes_audit_row(client: TestClient, database_url: str) -> None:
    auth = _auth(client)
    product = _create_product(client, auth, stock="1")
    assert _adjust(client, auth, product["id"], delta="2", reason="receipt").status_code == 201
    with db_session(database_url) as session:
        rows = list(session.scalars(select(AuditLog).where(AuditLog.action == "stock_adjusted")))
        assert rows
        assert rows[-1].workspace_id == UUID(str(auth["workspace"]["id"]))  # type: ignore[index]
