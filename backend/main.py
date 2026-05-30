"""Entry point do FastAPI - LATAM Analytics Platform (demo).

Boot:
    uvicorn main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import dashboards as dashboards_router
from app.routers import alerts as alerts_router
from app.routers import data_sources as data_sources_router
from app.routers import datasets as datasets_router
from app.routers import forecasts as forecasts_router
from app.routers import metrics as metrics_router
from app.routers import model_registry as model_registry_router
from app.routers import notifications as notifications_router
from app.routers import pipelines as pipelines_router
from app.routers import reports as reports_router
from app.routers import scheduled_jobs as scheduled_jobs_router
from app.routers import users as users_router
from app.routers import workspaces as workspaces_router
from config import settings
from database import init_db


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Demo da plataforma de analytics LATAM. "
        "Login simulado, RBAC central, datasets, ETL visual, dashboards, forecasting."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    from app.services.scheduler_service import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    from app.services.scheduler_service import stop_scheduler
    stop_scheduler()


@app.get("/", tags=["health"])
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(workspaces_router.router)
app.include_router(data_sources_router.router)
app.include_router(datasets_router.router)
app.include_router(metrics_router.router)
app.include_router(dashboards_router.router)
app.include_router(pipelines_router.router)
app.include_router(forecasts_router.router)
app.include_router(alerts_router.router)
app.include_router(model_registry_router.router)
app.include_router(notifications_router.router)
app.include_router(reports_router.router)
app.include_router(scheduled_jobs_router.router)
