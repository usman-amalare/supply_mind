"""Initial schema from SQLAlchemy metadata, plus append-only triggers.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-29

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

import supplymind.db.registry  # noqa: F401
from supplymind.db.base import Base

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REJECT_MUTATION = """
CREATE OR REPLACE FUNCTION supplymind_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'append-only table % cannot be modified', TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$;
"""


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())
    op.execute(_REJECT_MUTATION)
    op.execute(
        """
        CREATE TRIGGER stock_adjustments_append_only
        BEFORE UPDATE OR DELETE ON stock_adjustments
        FOR EACH ROW
        EXECUTE FUNCTION supplymind_reject_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION supplymind_reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS stock_adjustments_append_only ON stock_adjustments")
    op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
    Base.metadata.drop_all(op.get_bind())
    op.execute("DROP FUNCTION IF EXISTS supplymind_reject_mutation()")
