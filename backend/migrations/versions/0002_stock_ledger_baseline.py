"""One initial ledger entry per product, nonnegative balances, legacy baseline.

Revision ID: 0002_stock_ledger_baseline
Revises: 0001_initial_schema
Create Date: 2026-10-29

Products created before Stage 4 may have current_stock without a ledger row.
This revision inserts one reason=initial baseline per such product without
changing quantities. The note labels the row as a Stage 4 baseline, not
reconstructed history.

Constraint and index creation is idempotent: a fresh upgrade through
0001_initial_schema already creates them from the current SQLAlchemy models
via create_all. Older databases that applied 0001 before those model fields
existed still receive them here.

Downgrade drops the Stage 4 index and check constraints but does not delete
baseline rows.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_stock_ledger_baseline"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE products
            ADD CONSTRAINT ck_products_current_stock_non_negative
            CHECK (current_stock >= 0);
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE stock_adjustments
            ADD CONSTRAINT ck_stock_adjustments_balance_after_non_negative
            CHECK (balance_after >= 0);
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_adjustments_one_initial
        ON stock_adjustments (workspace_id, product_id)
        WHERE reason = 'initial'
        """
    )
    op.execute(
        """
        INSERT INTO stock_adjustments (
            id,
            workspace_id,
            product_id,
            delta,
            reason,
            note,
            actor_user_id,
            balance_after,
            source_ref,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            p.workspace_id,
            p.id,
            p.current_stock,
            'initial',
            'Stage 4 baseline for products that had stock before the ledger',
            NULL,
            p.current_stock,
            'stage4_backfill',
            now(),
            now()
        FROM products AS p
        WHERE NOT EXISTS (
            SELECT 1
            FROM stock_adjustments AS sa
            WHERE sa.workspace_id = p.workspace_id
              AND sa.product_id = p.id
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_stock_adjustments_one_initial")
    op.execute(
        """
        ALTER TABLE stock_adjustments
        DROP CONSTRAINT IF EXISTS ck_stock_adjustments_balance_after_non_negative
        """
    )
    op.execute(
        """
        ALTER TABLE products
        DROP CONSTRAINT IF EXISTS ck_products_current_stock_non_negative
        """
    )
