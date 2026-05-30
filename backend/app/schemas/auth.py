"""Schemas Pydantic para autenticação simulada."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    home_workspace: str
    is_active: bool


class LoginResponse(BaseModel):
    token: str
    user: UserOut
    permissions: dict
    menu: dict
