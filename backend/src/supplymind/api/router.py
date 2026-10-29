"""Versioned API router."""

from __future__ import annotations

from fastapi import APIRouter

from supplymind.modules.identity.router import protected_router, public_router
from supplymind.modules.workspaces.router import router as workspace_router

api_router = APIRouter()
api_router.include_router(public_router)
api_router.include_router(protected_router)
api_router.include_router(workspace_router)
