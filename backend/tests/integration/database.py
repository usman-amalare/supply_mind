"""Alembic helpers for schema tests."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config

from supplymind.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
_TEST_SECRET = "test-secret-value-0123456789abcd"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+psycopg2://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    cfg.set_main_option("prepend_sys_path", str(BACKEND_ROOT / "src"))
    return cfg


def _with_database_env(url: str, action: Callable[[Config], None]) -> None:
    previous = {key: os.environ.get(key) for key in ("APP_ENV", "APP_SECRET", "DATABASE_URL")}
    os.environ["APP_ENV"] = "test"
    os.environ["APP_SECRET"] = _TEST_SECRET
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    try:
        cfg = alembic_config()
        action(cfg)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def migrate(url: str, revision: str) -> None:
    """Upgrade to a revision, or downgrade to base when revision is ``base``."""

    def action(cfg: Config) -> None:
        if revision == "base":
            command.downgrade(cfg, "base")
        else:
            command.upgrade(cfg, revision)

    _with_database_env(url, action)


def downgrade(url: str, revision: str) -> None:
    """Downgrade to a specific revision (for example ``0001_initial_schema``)."""

    def action(cfg: Config) -> None:
        command.downgrade(cfg, revision)

    _with_database_env(url, action)
