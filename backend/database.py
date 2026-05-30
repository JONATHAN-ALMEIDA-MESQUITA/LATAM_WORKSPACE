"""Setup do SQLAlchemy para a demo (SQLite).

Estrutura preparada para troca por PostgreSQL apenas alterando `database_url`.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    """Base declarativa única para todos os models."""


# Para SQLite precisamos do connect_args com check_same_thread=False
# quando usamos múltiplas threads (FastAPI).
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """Dependency do FastAPI para injetar sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Cria todas as tabelas. Importa os models para registrá-los no metadata."""
    # Import lazy para evitar ciclo.
    from app.models import (  # noqa: F401
        alert,
        audit_log,
        dashboard,
        data_source,
        dataset,
        forecast,
        metric,
        pipeline,
        lineage,
        model_registry,
        quality,
        report,
        scheduled_job,
        user,
        workspace,
    )

    Base.metadata.create_all(bind=engine)
