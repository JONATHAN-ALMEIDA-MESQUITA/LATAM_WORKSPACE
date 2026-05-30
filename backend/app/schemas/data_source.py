"""Schemas Pydantic para DataSource."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# Usamos alias "schema" no JSON mas internamente "db_schema" para não conflitar
# com o método BaseModel.schema() do Pydantic v1 (warning deprecated em v2).
_SCHEMA_CONFIG = ConfigDict(populate_by_name=True)


class DataSourceCreate(BaseModel):
    model_config = _SCHEMA_CONFIG
    connection_name: str = Field(min_length=2, max_length=128)
    database_type: str  # PostgreSQL | SQL Server | MySQL | SQLite | DuckDB
    host: str = ""
    port: int = 0
    database_name: str = ""
    username: str = ""
    password: str = ""  # nunca persistido em texto puro
    db_schema: str = Field(default="", alias="schema")
    workspace: str = "LATAM"
    notes: str = ""


class DataSourceUpdate(BaseModel):
    model_config = _SCHEMA_CONFIG
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    db_schema: str | None = Field(default=None, alias="schema")
    status: str | None = None
    notes: str | None = None


class DataSourceOut(BaseModel):
    model_config = _SCHEMA_CONFIG
    id: int
    connection_name: str
    database_type: str
    host: str
    port: int
    database_name: str
    username: str
    has_password: bool
    db_schema: str = Field(default="", alias="schema", serialization_alias="schema")
    status: str
    workspace: str
    created_by: str
    created_at: datetime
    last_test_at: datetime | None = None
    notes: str


class TestConnectionResult(BaseModel):
    success: bool
    message: str
    latency_ms: int
