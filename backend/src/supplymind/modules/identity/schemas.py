"""Identity request and response models. Extra fields are rejected on writes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=10, max_length=128)
    workspace_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)
    password: SecretStr = Field(min_length=10, max_length=128)


class UserView(BaseModel):
    id: UUID
    email: str


class WorkspaceView(BaseModel):
    id: UUID
    name: str
    industry: str | None
    size_band: str | None
    timezone: str
    currency: str
    onboarding_step: str
    onboarding_completed_at: datetime | None


class AuthResponse(BaseModel):
    user: UserView
    workspace: WorkspaceView
    csrf_token: str


class CsrfResponse(BaseModel):
    csrf_token: str
