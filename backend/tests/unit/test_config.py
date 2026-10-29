from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from supplymind.config import Settings
from tests.support import build_settings


def test_required_settings_have_no_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_SECRET", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_placeholder_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build_settings(app_secret="password")
    with pytest.raises(ValidationError):
        build_settings(app_secret="x" * 31)


def test_sqlite_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url="sqlite:///local.db")


def test_plain_postgres_url_is_normalized_to_psycopg() -> None:
    settings = build_settings(
        database_url="postgresql://supplymind:supplymind@127.0.0.1:5432/supplymind"
    )
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_openai_model_and_prices_default_to_unset() -> None:
    settings = build_settings()
    assert settings.openai_model is None
    assert settings.openai_price_input_per_m is None
    assert settings.openai_price_output_per_m is None
    assert settings.ai_send_product_names is False
    assert settings.fx_provider == "manual"
    assert settings.explanations_configured() is False


def test_explanations_require_key_model_prices_and_caps() -> None:
    settings = build_settings(
        openai_api_key="test-key",
        openai_model="configured-by-env",
        openai_price_input_per_m=Decimal("1"),
        openai_price_output_per_m=Decimal("2"),
        ai_monthly_token_cap=1000,
        ai_monthly_cost_cap=Decimal("5"),
    )
    assert settings.explanations_configured() is True


def test_one_openai_price_without_the_other_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build_settings(openai_price_input_per_m=Decimal("1"))


def test_production_rejects_example_database_and_insecure_cookies() -> None:
    with pytest.raises(ValidationError):
        build_settings(
            app_env="production",
            app_secret="p" * 32,
            session_cookie_secure=True,
            frontend_origins="https://app.example.com",
        )
    with pytest.raises(ValidationError):
        build_settings(
            app_env="production",
            app_secret="p" * 32,
            database_url="postgresql+psycopg://app:other@db.internal:5432/supplymind",
            session_cookie_secure=False,
            frontend_origins="https://app.example.com",
        )
    with pytest.raises(ValidationError):
        build_settings(
            app_env="production",
            app_secret="p" * 32,
            database_url="postgresql+psycopg://app:other@db.internal:5432/supplymind",
            session_cookie_secure=True,
            frontend_origins="http://app.example.com",
        )


def test_wildcard_origin_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build_settings(frontend_origins="*")
