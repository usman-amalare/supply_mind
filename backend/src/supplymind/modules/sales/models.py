"""Sales tables. A covered day with no sales_daily row means zero sales, not missing data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from supplymind.db.base import Base
from supplymind.db.enums import CsvImportStatus, CsvRowStatus, pg_enum
from supplymind.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceIdMixin

JsonObject = dict[str, object]


class CsvImport(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "csv_imports"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_csv_imports_workspace_id"),
        CheckConstraint("row_count IS NULL OR row_count >= 0", name="row_count_non_negative"),
        CheckConstraint(
            "valid_row_count IS NULL OR valid_row_count >= 0",
            name="valid_row_count_non_negative",
        ),
        CheckConstraint(
            "error_row_count IS NULL OR error_row_count >= 0",
            name="error_row_count_non_negative",
        ),
    )

    status: Mapped[CsvImportStatus] = mapped_column(
        pg_enum(CsvImportStatus, "ck_csv_imports_status"),
        nullable=False,
    )
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_format: Mapped[str | None] = mapped_column(String(32))
    duplicate_policy: Mapped[str | None] = mapped_column(String(32))
    row_count: Mapped[int | None] = mapped_column(Integer)
    valid_row_count: Mapped[int | None] = mapped_column(Integer)
    error_row_count: Mapped[int | None] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)
    deduct_from_stock: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )


class CsvImportRow(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "csv_import_rows"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_csv_import_rows_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "import_id",
            "row_number",
            name="uq_csv_import_rows_import_row",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "import_id"],
            ["csv_imports.workspace_id", "csv_imports.id"],
            name="fk_csv_import_rows_import",
        ),
        CheckConstraint("row_number > 0", name="row_number_positive"),
    )

    import_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parsed: Mapped[JsonObject | None] = mapped_column(JSONB)
    status: Mapped[CsvRowStatus] = mapped_column(
        pg_enum(CsvRowStatus, "ck_csv_import_rows_status"),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(64))


class SalesDaily(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "sales_daily"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_sales_daily_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "product_id",
            "sale_date",
            name="uq_sales_daily_product_date",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_sales_daily_product",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "import_id"],
            ["csv_imports.workspace_id", "csv_imports.id"],
            name="fk_sales_daily_import",
        ),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
    )

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    import_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))


class SalesCoverage(UUIDPrimaryKeyMixin, WorkspaceIdMixin, TimestampMixin, Base):
    __tablename__ = "sales_coverage"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_sales_coverage_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_sales_coverage_product",
        ),
        CheckConstraint("covered_to >= covered_from", name="coverage_order"),
    )

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    covered_from: Mapped[date] = mapped_column(Date, nullable=False)
    covered_to: Mapped[date] = mapped_column(Date, nullable=False)
