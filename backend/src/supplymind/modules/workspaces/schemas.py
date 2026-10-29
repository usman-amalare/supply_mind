"""Workspace writes expose company name and notification prefs only.

Risk-engine fields stay at their schema defaults and are not part of this API.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkspacePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class NotificationPrefs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_emails: list[str] = Field(max_length=20)
    cooldown_hours: int = Field(ge=1, le=168)


class WorkspaceSettingsView(BaseModel):
    notification_prefs: NotificationPrefs


class WorkspaceSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_prefs: NotificationPrefs
