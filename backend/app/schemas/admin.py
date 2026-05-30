"""Schemas Admin panel (Phase 8)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AuditLogOut(BaseModel):
    id: int
    user_email: str
    action: str
    object_type: str
    object_name: str
    workspace: str
    business_area: str
    timestamp: datetime
    details: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    role: str
    home_workspace: str = "LATAM"


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = None
    home_workspace: str | None = None
    is_active: bool | None = None


class WorkspaceUpdate(BaseModel):
    description: str | None = None
    scope: str | None = None


class PermissionsMatrixOut(BaseModel):
    roles: list[str]
    capabilities: list[str]
    matrix: dict[str, list[str]]
    workspace_access: dict[str, list[str] | None]
    business_areas: dict[str, list[str] | None]


class SystemStatusOut(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database_url: str
    scheduler_running: bool
    scheduler_active_jobs: int
    entity_counts: dict[str, int]
    recent_failed_jobs: int
