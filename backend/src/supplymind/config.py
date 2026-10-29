"""Typed settings. Secrets have no code defaults. See docs/DECISIONS.md D-009 and D-010."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_FORBIDDEN_SECRETS = frozenset(
    {
        "change-me",
        "changeme",
        "secret",
        "password",
        "supplymind",
        "placeholder",
        "dev-secret",
        "test-secret",
    }
)
_EXAMPLE_DATABASE_CREDENTIALS = "supplymind:supplymind@"


def _env_file() -> str:
    return str(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"]
    app_secret: SecretStr
    database_url: str
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    frontend_origins: str = ""
    session_cookie_name: str = "supplymind_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_absolute_timeout_hours: int = Field(default=12, gt=0)
    session_idle_timeout_hours: int = Field(default=1, gt=0)
    csrf_header_name: str = "X-CSRF-Token"
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    openai_timeout_s: float = Field(default=30, gt=0)
    openai_price_input_per_m: Decimal | None = None
    openai_price_output_per_m: Decimal | None = None
    ai_send_product_names: bool = False
    ai_monthly_token_cap: int | None = None
    ai_monthly_cost_cap: Decimal | None = None
    csv_max_bytes: int = Field(default=5_000_000, gt=0)
    csv_max_rows: int = Field(default=50_000, gt=0)
    fx_provider: Literal["manual"] = "manual"
    fx_staleness_hours: int = Field(default=48, gt=0)
    fx_refresh_interval_hours: int = Field(default=6, gt=0)
    smtp_host: str | None = None
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = False

    @field_validator(
        "openai_model",
        "smtp_host",
        "smtp_username",
        "smtp_from",
        mode="before",
    )
    @classmethod
    def blank_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator(
        "openai_api_key",
        "smtp_password",
        "openai_price_input_per_m",
        "openai_price_output_per_m",
        "ai_monthly_token_cap",
        "ai_monthly_cost_cap",
        mode="before",
    )
    @classmethod
    def blank_optional_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def postgresql_url(cls, value: str) -> str:
        if value.startswith("postgresql+psycopg2://"):
            value = "postgresql+psycopg://" + value.removeprefix("postgresql+psycopg2://")
        elif value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value.removeprefix("postgresql://")
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
        return value

    @field_validator("ai_monthly_token_cap")
    @classmethod
    def token_cap_non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("AI monthly token cap cannot be negative")
        return value

    @field_validator("ai_monthly_cost_cap", "openai_price_input_per_m", "openai_price_output_per_m")
    @classmethod
    def money_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("amounts cannot be negative")
        return value

    @model_validator(mode="after")
    def check_secrets_and_origins(self) -> Self:
        secret = self.app_secret.get_secret_value()
        if len(secret) < 32 or secret != secret.strip() or secret.casefold() in _FORBIDDEN_SECRETS:
            raise ValueError(
                "APP_SECRET must be at least 32 characters and must not be a placeholder"
            )
        origins = self.frontend_origin_list()
        if any(origin == "*" for origin in origins):
            raise ValueError("FRONTEND_ORIGINS cannot contain a wildcard")
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SameSite=None requires SESSION_COOKIE_SECURE=true")
        prices = (self.openai_price_input_per_m, self.openai_price_output_per_m)
        if (prices[0] is None) != (prices[1] is None):
            raise ValueError("Set both OpenAI token prices, or leave both empty")
        if self.app_env == "production":
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production")
            if not origins or any(not origin.startswith("https://") for origin in origins):
                raise ValueError("Production FRONTEND_ORIGINS must list https origins")
            if _EXAMPLE_DATABASE_CREDENTIALS in self.database_url:
                raise ValueError("DATABASE_URL still uses the local example credentials")
        return self

    def frontend_origin_list(self) -> list[str]:
        return [item.strip() for item in self.frontend_origins.split(",") if item.strip()]

    def explanations_configured(self) -> bool:
        """True only when a key, model, both prices, and both caps are set.

        No model id, price, or cap is assumed. Live explanation calls stay off until then.
        """
        key = self.openai_api_key.get_secret_value().strip() if self.openai_api_key else ""
        return bool(
            key
            and self.openai_model
            and self.openai_price_input_per_m is not None
            and self.openai_price_output_per_m is not None
            and self.ai_monthly_token_cap is not None
            and self.ai_monthly_cost_cap is not None
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Required values come from the environment. mypy cannot see that.
    return Settings()  # type: ignore[call-arg]
