from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict

from supplymind.core.errors import AppError
from supplymind.core.pagination import PageParams
from supplymind.main import create_app
from tests.support import build_settings

_REQUEST_ID = "abcDEF123"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = _app_with_probes(create_app(build_settings()))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _app_with_probes(app: FastAPI) -> FastAPI:
    class Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str

    @app.post("/api/v1/_validation_probe")
    def validation_probe(payload: Payload) -> dict[str, str]:
        return {"name": payload.name}

    @app.get("/api/v1/_page_probe")
    def page_probe(params: Annotated[PageParams, Depends()]) -> dict[str, int]:
        return {"page": params.page, "page_size": params.page_size}

    @app.get("/api/v1/_app_error")
    def app_error() -> None:
        raise AppError("example_failed", "Example failed", status_code=409)

    @app.get("/api/v1/_boom")
    def boom() -> None:
        raise RuntimeError("boom-secret-marker")

    return app


async def test_health_headers_and_request_id(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": _REQUEST_ID})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == _REQUEST_ID
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers


async def test_invalid_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "bad id"})
    assert response.headers["x-request-id"] != "bad id"
    assert " " not in response.headers["x-request-id"]


async def test_unknown_route_uses_the_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/missing")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"]


async def test_validation_error_omits_submitted_values(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/_validation_probe", json={"name": "ok", "extra": "secret"}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "secret" not in response.text


async def test_page_size_cap(client: AsyncClient) -> None:
    response = await client.get("/api/v1/_page_probe", params={"page_size": 101})
    assert response.status_code == 422


async def test_app_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/_app_error")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "example_failed"


def test_unhandled_error_hides_the_exception_text() -> None:
    # Starlette re-raises after sending the 500 so servers can log it.
    # raise_server_exceptions=False is how the response body is observed.
    app = _app_with_probes(create_app(build_settings()))
    with TestClient(app, raise_server_exceptions=False) as http:
        response = http.get("/api/v1/_boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "boom-secret-marker" not in response.text
    assert "Traceback" not in response.text


async def test_cors_echoes_a_configured_origin() -> None:
    app = create_app(build_settings(frontend_origins="http://localhost:5173"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_production_sends_hsts_and_hides_openapi() -> None:
    settings = build_settings(
        app_env="production",
        app_secret="p" * 32,
        database_url="postgresql+psycopg://app:other@db.internal:5432/supplymind",
        frontend_origins="https://app.example.com",
        session_cookie_secure=True,
    )
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        health = await http.get("/health")
        schema = await http.get("/openapi.json")
    assert "strict-transport-security" in health.headers
    assert schema.status_code == 404


def test_source_does_not_hardcode_a_model_or_secret_prefix() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "supplymind"
    banned = ("gpt-4", "gpt-3.5", "text-davinci", "sk-proj", "sk-live")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in banned:
            assert token not in text
