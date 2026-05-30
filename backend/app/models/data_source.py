"""Model de DataSource - conexões com bancos cadastradas no Builder Studio.

Para a demo a conexão é simulada (não conectamos nos bancos externos).
Senhas NÃO são persistidas em texto puro - guardamos só um marcador.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class DatabaseType(str, Enum):
    POSTGRESQL = "PostgreSQL"
    SQL_SERVER = "SQL Server"
    MYSQL = "MySQL"
    SQLITE = "SQLite"
    DUCKDB = "DuckDB"


class DataSourceStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PENDING_TEST = "Pending Test"
    ERROR = "Error"


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    database_type: Mapped[str] = mapped_column(String(32), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    database_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    username: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # NUNCA gravamos a senha real. Marcador apenas para indicar "tem senha".
    has_password: Mapped[bool] = mapped_column(default=False, nullable=False)
    db_schema: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DataSourceStatus.PENDING_TEST.value)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, default="LATAM")
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "connection_name": self.connection_name,
            "database_type": self.database_type,
            "host": self.host,
            "port": self.port,
            "database_name": self.database_name,
            "username": self.username,
            "has_password": self.has_password,
            "schema": self.db_schema,
            "status": self.status,
            "workspace": self.workspace,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_test_at": self.last_test_at.isoformat() if self.last_test_at else None,
            "notes": self.notes,
        }
