"""Schema invariants from Sections 8.2 and 9. These tests require PostgreSQL 16."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session

import supplymind.db.registry  # noqa: F401
from supplymind.db.base import Base
from supplymind.db.enums import (
    AlertStatus,
    AlertType,
    OrderStatus,
    RiskBand,
    StockReason,
    VendorRole,
)
from supplymind.db.session import make_engine, make_session_factory
from supplymind.modules.alerts.models import Alert
from supplymind.modules.audit.models import AuditLog
from supplymind.modules.catalog.models import Product, ProductVendor, Vendor
from supplymind.modules.identity.models import User
from supplymind.modules.inventory.models import StockAdjustment
from supplymind.modules.orders.models import Order
from supplymind.modules.risk.models import RiskSnapshot
from supplymind.modules.workspaces.models import Workspace
from tests.integration.database import migrate

EXPECTED_TABLES = {
    "ai_usage",
    "alerts",
    "audit_log",
    "csv_import_rows",
    "csv_imports",
    "explanations",
    "fx_rates",
    "jobs",
    "memberships",
    "notifications",
    "order_lines",
    "orders",
    "password_reset_tokens",
    "product_vendors",
    "products",
    "risk_snapshots",
    "sales_coverage",
    "sales_daily",
    "seasonal_events",
    "sessions",
    "stock_adjustments",
    "users",
    "vendors",
    "workspace_settings",
    "workspaces",
}


@pytest.fixture
def session(database_url: str) -> Iterator[Session]:
    engine = make_engine(database_url)
    db = make_session_factory(engine)()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def _workspace(db: Session, name: str) -> Workspace:
    row = Workspace(name=name)
    db.add(row)
    db.flush()
    return row


def _vendor(db: Session, workspace_id: object, name: str) -> Vendor:
    row = Vendor(workspace_id=workspace_id, name=name, typical_lead_time_days=7)
    db.add(row)
    db.flush()
    return row


def _product(db: Session, workspace_id: object, sku: str) -> Product:
    row = Product(
        workspace_id=workspace_id,
        sku=sku,
        name="Item",
        unit="each",
        reorder_threshold=Decimal("1.000"),
    )
    db.add(row)
    db.flush()
    return row


def test_migrated_schema_matches_models(database_url: str) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    engine = make_engine(database_url)
    with engine.connect() as connection:
        names = set(inspect(connection).get_table_names())
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)
        triggers = set(
            connection.execute(
                text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
            ).scalars()
        )
    engine.dispose()
    assert EXPECTED_TABLES <= names
    assert diff == [], diff
    assert "stock_adjustments_append_only" in triggers
    assert "audit_log_append_only" in triggers


def test_cross_workspace_product_link_is_rejected(session: Session) -> None:
    left = _workspace(session, "Left")
    right = _workspace(session, "Right")
    product = _product(session, left.id, "SKU-1")
    vendor = _vendor(session, right.id, "Other vendor")
    session.add(
        ProductVendor(
            workspace_id=right.id,
            product_id=product.id,
            vendor_id=vendor.id,
            role=VendorRole.PRIMARY,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_sku_uniqueness_is_case_insensitive_per_workspace(session: Session) -> None:
    left = _workspace(session, "Left")
    right = _workspace(session, "Right")
    _product(session, left.id, "AbC")
    _product(session, right.id, "abc")
    with pytest.raises(IntegrityError):
        _product(session, left.id, "abc")


def test_email_uniqueness_is_case_insensitive(session: Session) -> None:
    session.add(User(email="Owner@Example.com", password_hash="not-a-real-hash"))
    session.flush()
    session.add(User(email="owner@example.com", password_hash="not-a-real-hash"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_delivered_order_requires_an_actual_date(session: Session) -> None:
    workspace = _workspace(session, "Shop")
    vendor = _vendor(session, workspace.id, "Vendor")
    session.add(
        Order(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            order_date=date(2026, 1, 1),
            expected_date=date(2026, 1, 8),
            status=OrderStatus.DELIVERED,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_invalid_order_status_is_rejected_by_the_database(session: Session) -> None:
    workspace = _workspace(session, "Shop")
    vendor = _vendor(session, workspace.id, "Vendor")
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                """
                INSERT INTO orders (
                    id, workspace_id, vendor_id, order_date, expected_date, status,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :workspace_id, :vendor_id,
                    DATE '2026-01-01', DATE '2026-01-08', 'teleported',
                    now(), now()
                )
                """
            ),
            {"workspace_id": workspace.id, "vendor_id": vendor.id},
        )


def test_open_alert_dedupe_is_unique_until_resolved(session: Session) -> None:
    workspace = _workspace(session, "Shop")
    product = _product(session, workspace.id, "SKU-9")
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    snapshot = RiskSnapshot(
        workspace_id=workspace.id,
        product_id=product.id,
        computed_at=opened,
        inputs_hash="a" * 64,
        engine_version="test",
        evidence={},
        contributions={},
        data_quality={},
    )
    session.add(snapshot)
    session.flush()
    first = Alert(
        workspace_id=workspace.id,
        product_id=product.id,
        snapshot_id=snapshot.id,
        alert_type=AlertType.STOCKOUT_RISK,
        severity=RiskBand.HIGH,
        status=AlertStatus.OPEN,
        opened_at=opened,
        dedupe_key="sku-9:stockout_risk",
    )
    session.add(first)
    session.flush()
    session.add(
        Alert(
            workspace_id=workspace.id,
            product_id=product.id,
            snapshot_id=snapshot.id,
            alert_type=AlertType.STOCKOUT_RISK,
            severity=RiskBand.HIGH,
            status=AlertStatus.OPEN,
            opened_at=opened,
            dedupe_key="sku-9:stockout_risk",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_stock_adjustment_update_is_rejected(session: Session) -> None:
    workspace = _workspace(session, "Shop")
    product = _product(session, workspace.id, "SKU-2")
    adjustment = StockAdjustment(
        workspace_id=workspace.id,
        product_id=product.id,
        delta=Decimal("2"),
        reason=StockReason.INITIAL,
        balance_after=Decimal("2"),
    )
    session.add(adjustment)
    session.flush()
    with pytest.raises(DatabaseError, match="append-only"):
        session.execute(
            text("UPDATE stock_adjustments SET note = 'changed' WHERE id = :id"),
            {"id": adjustment.id},
        )


def test_audit_log_delete_is_rejected(session: Session) -> None:
    row = AuditLog(action="sign_in", entity_type="user")
    session.add(row)
    session.flush()
    with pytest.raises(DatabaseError, match="append-only"):
        session.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": row.id})


def test_migration_downgrade_and_upgrade(database_url: str) -> None:
    migrate(database_url, "base")
    try:
        engine = make_engine(database_url)
        with engine.connect() as connection:
            present = connection.execute(text("SELECT to_regclass('public.products')")).scalar()
        engine.dispose()
        assert present is None
    finally:
        migrate(database_url, "head")
