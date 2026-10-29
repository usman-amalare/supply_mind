"""Page envelope from Section 7. page_size cannot exceed 100."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class Page[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
