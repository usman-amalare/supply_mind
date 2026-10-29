from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from supplymind.api.csrf_policy import CSRF_EXEMPT_PATHS, UNSAFE_METHODS
from supplymind.main import create_app
from tests.support import build_settings

# Tenant-data routes that exist in this stage, and the tests that isolate them.
# Adding a product, vendor, or other tenant route without an entry fails this test.
ISOLATION_TESTS = {
    ("GET", "/api/v1/workspace"): "test_workspace_query_cannot_switch_tenant",
    ("PATCH", "/api/v1/workspace"): "test_workspace_body_cannot_switch_tenant",
    ("GET", "/api/v1/workspace/settings"): "test_settings_are_isolated_between_workspaces",
    ("PATCH", "/api/v1/workspace/settings"): "test_settings_patch_cannot_change_another_workspace",
    ("GET", "/api/v1/vendors"): "test_vendors_list_cannot_see_other_workspace",
    ("POST", "/api/v1/vendors"): "test_catalog_create_rejects_foreign_workspace_id",
    ("GET", "/api/v1/vendors/{vendor_id}"): "test_vendors_list_cannot_see_other_workspace",
    ("PATCH", "/api/v1/vendors/{vendor_id}"): "test_vendors_list_cannot_see_other_workspace",
    ("POST", "/api/v1/vendors/{vendor_id}/archive"): "test_vendors_list_cannot_see_other_workspace",
    ("GET", "/api/v1/products"): "test_products_list_cannot_see_other_workspace",
    ("POST", "/api/v1/products"): "test_catalog_create_rejects_foreign_workspace_id",
    ("GET", "/api/v1/products/{product_id}"): "test_products_list_cannot_see_other_workspace",
    ("PATCH", "/api/v1/products/{product_id}"): "test_products_list_cannot_see_other_workspace",
    (
        "POST",
        "/api/v1/products/{product_id}/archive",
    ): "test_products_list_cannot_see_other_workspace",
    ("GET", "/api/v1/products/{product_id}/vendors"): "test_cannot_link_foreign_vendor_or_product",
    (
        "PUT",
        "/api/v1/products/{product_id}/vendors/{role}",
    ): "test_product_vendors_assign_isolation",
    (
        "DELETE",
        "/api/v1/products/{product_id}/vendors/{role}",
    ): "test_product_vendors_remove_isolation",
    (
        "POST",
        "/api/v1/products/{product_id}/stock-adjustments",
    ): "test_stock_routes_are_isolated",
    (
        "GET",
        "/api/v1/products/{product_id}/stock-adjustments",
    ): "test_stock_routes_are_isolated",
    ("GET", "/api/v1/products/{product_id}/stock"): "test_stock_summary_isolation",
}


def _iter_api_routes(app: FastAPI) -> list[tuple[str, APIRoute]]:
    found: list[tuple[str, APIRoute]] = []

    def walk(routes: list[object], prefix: str) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                path = route.path
                if not path.startswith("/"):
                    path = "/" + path
                found.append((prefix + path, route))
                continue
            original = getattr(route, "original_router", None)
            context = getattr(route, "include_context", None)
            if original is None or context is None:
                continue
            child_prefix = prefix + str(getattr(context, "prefix", "") or "")
            walk(list(original.routes), child_prefix)

    walk(list(app.routes), "")
    return found


def _dependency_names(route: APIRoute) -> set[str]:
    names: set[str] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        item = stack.pop()
        call = item.call
        name = getattr(call, "__name__", "")
        if isinstance(name, str) and name:
            names.add(name)
        stack.extend(item.dependencies)
    for depends in route.dependencies:
        call = depends.dependency
        name = getattr(call, "__name__", "")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def test_unsafe_routes_require_csrf_or_are_explicitly_exempt() -> None:
    app = create_app(build_settings())
    api_routes = [
        (path, route) for path, route in _iter_api_routes(app) if path.startswith("/api/v1")
    ]
    assert api_routes
    for path, route in api_routes:
        methods = route.methods or set()
        if not methods & UNSAFE_METHODS:
            continue
        names = _dependency_names(route)
        if path in CSRF_EXEMPT_PATHS:
            assert "require_csrf" not in names, path
        else:
            assert "require_csrf" in names, path


def test_new_api_routes_are_auth_or_have_an_isolation_test() -> None:
    import tests.integration.test_catalog as catalog_tests
    import tests.integration.test_identity as identity_tests
    import tests.integration.test_inventory as inventory_tests

    modules = (identity_tests, catalog_tests, inventory_tests)
    app = create_app(build_settings())
    api_routes = [
        (path, route) for path, route in _iter_api_routes(app) if path.startswith("/api/v1")
    ]
    assert api_routes
    for path, route in api_routes:
        if path.startswith("/api/v1/auth/"):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            test_name = ISOLATION_TESTS.get((method, path))
            assert test_name is not None, f"{method} {path} has no isolation test"
            assert any(hasattr(module, test_name) for module in modules), test_name


def test_argon2_defaults_match_the_rfc9106_low_memory_profile() -> None:
    settings = build_settings()
    assert settings.argon2_time_cost == 3
    assert settings.argon2_memory_cost == 65536
    assert settings.argon2_parallelism == 4
    assert settings.password_reset_ttl_minutes == 30
