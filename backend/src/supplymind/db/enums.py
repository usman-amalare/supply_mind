"""String values stored in PostgreSQL checks. See docs/DECISIONS.md D-007."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class OnboardingStep(StrEnum):
    COMPANY = "company"
    VENDORS = "vendors"
    PRODUCTS = "products"
    SALES_HISTORY = "sales_history"
    RISK_FACTORS = "risk_factors"
    FINISH = "finish"


class MembershipRole(StrEnum):
    OWNER = "owner"


class VendorRole(StrEnum):
    PRIMARY = "primary"
    BACKUP = "backup"


class StockReason(StrEnum):
    MANUAL_COUNT = "manual_count"
    RECEIPT = "receipt"
    SALE_DEDUCTION = "sale_deduction"
    DAMAGE = "damage"
    CORRECTION = "correction"
    INITIAL = "initial"


class CsvImportStatus(StrEnum):
    UPLOADED = "uploaded"
    PREVIEWED = "previewed"
    COMMITTED = "committed"
    FAILED = "failed"
    EXPIRED = "expired"


class CsvRowStatus(StrEnum):
    VALID = "valid"
    ERROR = "error"
    DUPLICATE = "duplicate"
    UNKNOWN_SKU = "unknown_sku"


class OrderStatus(StrEnum):
    OPEN = "open"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    AUTO_RESOLVED = "auto_resolved"


class AlertType(StrEnum):
    STOCKOUT_RISK = "stockout_risk"
    REORDER_POINT_REACHED = "reorder_point_reached"


class ExplanationSource(StrEnum):
    AI = "ai"
    FALLBACK = "fallback"


class NotificationEvent(StrEnum):
    OPENED = "opened"
    ESCALATED = "escalated"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=40,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
