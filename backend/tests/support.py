"""Settings builder for tests. Values are passed explicitly so ambient env vars do not leak in."""

from __future__ import annotations

from supplymind.config import Settings


def build_settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "app_env": "test",
        "app_secret": "test-secret-value-0123456789abcd",
        "database_url": "postgresql+psycopg://supplymind:supplymind@127.0.0.1:5432/supplymind",
    }
    data.update(overrides)
    return Settings.model_validate(data)
