"""Import every model so Base.metadata is complete. Alembic and tests import this module."""

from __future__ import annotations

from supplymind.modules.alerts.models import Alert
from supplymind.modules.audit.models import AuditLog
from supplymind.modules.catalog.models import Product, ProductVendor, Vendor
from supplymind.modules.explanations.models import AiUsage, Explanation
from supplymind.modules.identity.models import PasswordResetToken, Session, User
from supplymind.modules.inventory.models import StockAdjustment
from supplymind.modules.jobs.models import Job
from supplymind.modules.notifications.models import Notification
from supplymind.modules.orders.models import Order, OrderLine
from supplymind.modules.risk.models import RiskSnapshot
from supplymind.modules.sales.models import CsvImport, CsvImportRow, SalesCoverage, SalesDaily
from supplymind.modules.signals.models import FxRate, SeasonalEvent
from supplymind.modules.workspaces.models import Membership, Workspace, WorkspaceSettings

__all__ = [
    "AiUsage",
    "Alert",
    "AuditLog",
    "CsvImport",
    "CsvImportRow",
    "Explanation",
    "FxRate",
    "Job",
    "Membership",
    "Notification",
    "Order",
    "OrderLine",
    "PasswordResetToken",
    "Product",
    "ProductVendor",
    "RiskSnapshot",
    "SalesCoverage",
    "SalesDaily",
    "SeasonalEvent",
    "Session",
    "StockAdjustment",
    "User",
    "Vendor",
    "Workspace",
    "WorkspaceSettings",
]
