"""Schemas Pydantic para Workspaces."""

from __future__ import annotations

from pydantic import BaseModel


class WorkspaceOut(BaseModel):
    id: int
    name: str
    description: str
    scope: str
