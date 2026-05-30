"""Configuração central da aplicação.

Mantida simples para a demo, mas com pydantic-settings para poder
ser estendida facilmente (env vars, .env files, Postgres em produção, etc.).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LATAM Analytics Platform"
    app_version: str = "0.1.0-demo"
    environment: str = "demo"

    # SQLite local na demo. Estrutura pronta para trocar por Postgres.
    database_url: str = f"sqlite:///{(BASE_DIR / 'latam_analytics.db').as_posix()}"

    # CORS - origens permitidas (frontend Vite em dev).
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Diretórios de storage.
    upload_dir: Path = STORAGE_DIR / "uploads"
    processed_dir: Path = STORAGE_DIR / "processed"
    exports_dir: Path = STORAGE_DIR / "exports"
    sample_data_dir: Path = STORAGE_DIR / "sample_data"
    notifications_log_dir: Path = STORAGE_DIR / "notifications"

    # Token "fake" para a demo - login simulado.
    demo_token_prefix: str = "demo-token::"


settings = Settings()

for d in (
    settings.upload_dir,
    settings.processed_dir,
    settings.exports_dir,
    settings.sample_data_dir,
    settings.notifications_log_dir,
):
    d.mkdir(parents=True, exist_ok=True)
