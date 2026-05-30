"""Serviço central de permissões (RBAC).

Concentra TODA a lógica de "quem pode fazer o quê".
Tanto o backend (validação) quanto o frontend (montagem de menu) usam isso.

Regra principal: backend é sempre source of truth - frontend só esconde UI.
"""

from __future__ import annotations

from typing import Iterable

from app.models.user import Role
from app.models.workspace import BusinessArea, WorkspaceName


# -------------------------------------------------------------------------- #
# Capabilities centralizadas - cada role recebe um conjunto de capabilities  #
# textuais. Mais fácil de evoluir do que checar role.value em vários pontos. #
# -------------------------------------------------------------------------- #

ROLE_CAPABILITIES: dict[str, set[str]] = {
    Role.PLATFORM_ADMIN.value: {
        "view_builder_studio",
        "view_business_portal",
        "view_admin",
        "view_datasets",
        "view_data_sources",
        "view_metrics",
        "view_dashboards",
        "view_pipelines",
        "view_forecasts",
        "create_forecast",
        "publish_forecast",
        "view_alerts",
        "create_alert",
        "manage_alerts",
        "upload_dataset",
        "create_data_source",
        "certify_dataset",
        "create_etl",
        "create_pipeline",
        "run_pipeline",
        "publish_pipeline",
        "create_metric",
        "create_dashboard",
        "create_report",
        "run_forecast",
        "schedule_job",
        "submit_for_approval",
        "publish_any",
        "export_data",
        "manage_users",
        "manage_workspaces",
        "manage_permissions",
        "view_audit_logs",
        "view_lineage",
        "run_quality_checks",
        "export_dashboard",
        "view_model_registry",
        "register_model",
    },
    Role.DATA_DEVELOPER.value: {
        "view_builder_studio",
        "view_business_portal",
        "view_datasets",
        "view_data_sources",
        "view_metrics",
        "view_dashboards",
        "view_pipelines",
        "view_forecasts",
        "create_forecast",
        "view_alerts",
        "create_alert",
        "upload_dataset",
        "create_data_source",
        "certify_dataset",
        "create_etl",
        "create_pipeline",
        "run_pipeline",
        "publish_pipeline",
        "create_metric",
        "create_dashboard",
        "create_report",
        "run_forecast",
        "schedule_job",
        "submit_for_approval",
        "export_data",
        "view_lineage",
        "run_quality_checks",
        "export_dashboard",
        "view_model_registry",
        "register_model",
    },
    Role.DATA_ANALYST.value: {
        "view_builder_studio",
        "view_business_portal",
        "view_datasets",
        "view_data_sources",
        "view_metrics",
        "view_dashboards",
        "view_pipelines",
        "view_forecasts",
        "create_forecast",
        "view_alerts",
        "create_alert",
        "upload_dataset",
        "create_etl",
        "create_pipeline",
        "run_pipeline",
        "create_metric",
        "create_dashboard",
        "create_report",
        "submit_for_approval",
        "export_data",
        "view_lineage",
        "run_quality_checks",
    },
    Role.FINANCE_OWNER.value: {
        "view_builder_studio",
        "view_business_portal",
        "view_datasets",
        "view_metrics",
        "view_dashboards",
        "view_alerts",
        "create_alert",
        "create_dashboard",
        "create_metric",
        "certify_dataset",
        "submit_for_approval",
        "publish_finance",
        "export_data",
        "export_dashboard",
    },
    Role.OPERATIONS_OWNER.value: {
        "view_builder_studio",
        "view_business_portal",
        "view_datasets",
        "view_metrics",
        "view_dashboards",
        "view_alerts",
        "create_alert",
        "create_dashboard",
        "create_metric",
        "certify_dataset",
        "submit_for_approval",
        "publish_operations",
        "export_data",
    },
    Role.LATAM_EXECUTIVE_VIEWER.value: {
        "view_business_portal",
        "view_dashboards",
        "view_latam_executive",
        "view_alerts",
    },
    Role.VIEWER.value: {
        "view_business_portal",
        "view_dashboards",
        "view_alerts",
    },
    Role.ML_OWNER.value: {
        "view_builder_studio",
        "view_business_portal",
        "view_datasets",
        "view_metrics",
        "view_dashboards",
        "view_forecasts",
        "create_forecast",
        "run_forecast",
        "publish_forecast",
        "view_alerts",
        "create_alert",
        "export_data",
        "view_lineage",
        "view_model_registry",
        "register_model",
        "export_dashboard",
    },
}


# Workspaces que cada role pode acessar.
# None = todos. Caso contrário, lista explícita.
ROLE_WORKSPACE_ACCESS: dict[str, set[str] | None] = {
    Role.PLATFORM_ADMIN.value: None,
    Role.DATA_DEVELOPER.value: None,
    Role.DATA_ANALYST.value: {WorkspaceName.BRAZIL.value},
    Role.FINANCE_OWNER.value: None,
    Role.OPERATIONS_OWNER.value: None,
    Role.LATAM_EXECUTIVE_VIEWER.value: {WorkspaceName.LATAM.value},
    Role.VIEWER.value: {WorkspaceName.BRAZIL.value},
    Role.ML_OWNER.value: None,
}


# Business areas que cada role pode consumir (Business Portal).
ROLE_BUSINESS_AREAS: dict[str, set[str] | None] = {
    Role.PLATFORM_ADMIN.value: None,
    Role.DATA_DEVELOPER.value: None,
    Role.DATA_ANALYST.value: None,
    Role.FINANCE_OWNER.value: {BusinessArea.FINANCE.value, BusinessArea.LATAM_EXECUTIVE.value},
    Role.OPERATIONS_OWNER.value: {BusinessArea.OPERATIONS.value, BusinessArea.LATAM_EXECUTIVE.value},
    Role.LATAM_EXECUTIVE_VIEWER.value: {BusinessArea.LATAM_EXECUTIVE.value},
    Role.VIEWER.value: {
        BusinessArea.OPERATIONS.value,
        BusinessArea.FINANCE.value,
        BusinessArea.SUPPLIER.value,
        BusinessArea.SALES.value,
    },
    Role.ML_OWNER.value: None,
}


# -------------------------------------------------------------------------- #
# Funções utilitárias                                                        #
# -------------------------------------------------------------------------- #

def _caps(role: str) -> set[str]:
    return ROLE_CAPABILITIES.get(role, set())


def has_capability(user, capability: str) -> bool:
    return capability in _caps(user.role)


def has_any_capability(user, capabilities: Iterable[str]) -> bool:
    caps = _caps(user.role)
    return any(c in caps for c in capabilities)


def accessible_workspaces(user, all_workspaces: list[str]) -> list[str]:
    allowed = ROLE_WORKSPACE_ACCESS.get(user.role)
    if allowed is None:
        return all_workspaces
    return [w for w in all_workspaces if w in allowed]


def accessible_business_areas(user, all_areas: list[str]) -> list[str]:
    allowed = ROLE_BUSINESS_AREAS.get(user.role)
    if allowed is None:
        return all_areas
    return [a for a in all_areas if a in allowed]


# -------------------------------------------------------------------------- #
# API "can_*" - usada em routers e na geração de menus                       #
# -------------------------------------------------------------------------- #

def can_view_builder_studio(user) -> bool:
    return has_capability(user, "view_builder_studio")


def can_view_business_portal(user) -> bool:
    return has_capability(user, "view_business_portal")


def can_access_admin(user) -> bool:
    return has_capability(user, "view_admin")


def can_upload_dataset(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "upload_dataset"):
        return False
    return _workspace_ok(user, workspace)


def can_create_etl(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "create_etl"):
        return False
    return _workspace_ok(user, workspace)


def can_create_metric(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "create_metric"):
        return False
    return _workspace_ok(user, workspace)


def can_create_dashboard(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "create_dashboard"):
        return False
    return _workspace_ok(user, workspace)


def can_publish_dashboard(user, workspace: str | None, business_area: str | None) -> bool:
    if has_capability(user, "publish_any"):
        return True
    if business_area == BusinessArea.FINANCE.value and has_capability(user, "publish_finance"):
        return _workspace_ok(user, workspace)
    if business_area == BusinessArea.OPERATIONS.value and has_capability(user, "publish_operations"):
        return _workspace_ok(user, workspace)
    return False


def can_view_business_area(user, workspace: str | None, business_area: str) -> bool:
    if not can_view_business_portal(user):
        return False
    if not _workspace_ok(user, workspace):
        return False
    allowed = ROLE_BUSINESS_AREAS.get(user.role)
    if allowed is None:
        return True
    return business_area in allowed


def can_view_datasets(user) -> bool:
    return has_capability(user, "view_datasets")


def can_certify_dataset(user, business_area: str | None = None) -> bool:
    """Certificar pode quem tem capability geral OU é owner da área."""
    if has_capability(user, "certify_dataset"):
        return True
    if business_area == BusinessArea.FINANCE.value and has_capability(user, "publish_finance"):
        return True
    if business_area == BusinessArea.OPERATIONS.value and has_capability(user, "publish_operations"):
        return True
    return False


def can_view_data_sources(user) -> bool:
    return has_capability(user, "view_data_sources")


def can_create_data_source(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "create_data_source"):
        return False
    return _workspace_ok(user, workspace)


def can_run_forecast(user) -> bool:
    return has_capability(user, "run_forecast")


def can_export_data(user) -> bool:
    return has_capability(user, "export_data")


def can_submit_for_approval(user) -> bool:
    return has_capability(user, "submit_for_approval")


def can_view_pipelines(user) -> bool:
    return has_capability(user, "view_pipelines")


def can_create_pipeline(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "create_pipeline"):
        return False
    return _workspace_ok(user, workspace)


def can_run_pipeline(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "run_pipeline"):
        return False
    return _workspace_ok(user, workspace)


def can_publish_pipeline(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "publish_pipeline") and not has_capability(user, "publish_any"):
        return False
    return _workspace_ok(user, workspace)


def can_view_forecasts(user) -> bool:
    return has_capability(user, "view_forecasts")


def can_create_forecast(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "create_forecast"):
        return False
    return _workspace_ok(user, workspace)


def can_publish_forecast(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "publish_forecast") and not has_capability(user, "publish_any"):
        return False
    return _workspace_ok(user, workspace)


def can_view_alerts(user) -> bool:
    return has_capability(user, "view_alerts")


def can_create_alert(user, workspace: str | None = None) -> bool:
    if not has_capability(user, "create_alert"):
        return False
    return _workspace_ok(user, workspace)


def can_manage_alerts(user) -> bool:
    return has_capability(user, "manage_alerts")


def _workspace_ok(user, workspace: str | None) -> bool:
    if workspace is None:
        return True
    allowed = ROLE_WORKSPACE_ACCESS.get(user.role)
    if allowed is None:
        return True
    return workspace in allowed


# -------------------------------------------------------------------------- #
# Geração de menu (frontend consome via /auth/login)                         #
# -------------------------------------------------------------------------- #

ALL_WORKSPACES = [w.value for w in WorkspaceName]
ALL_BUSINESS_AREAS = [a.value for a in BusinessArea]


def build_user_menu(user) -> dict:
    """Retorna a estrutura de menu que o frontend deve exibir.

    Frontend usa para esconder/mostrar itens. Backend valida cada endpoint
    individualmente - não confia só no menu.
    """
    builder_items: list[dict] = []
    if can_view_builder_studio(user):
        builder_items = [
            {"key": "data-sources", "label": "Data Sources", "path": "/builder/data-sources"},
            {"key": "upload-data", "label": "Upload Data", "path": "/builder/upload-data"},
            {"key": "dataset-explorer", "label": "Dataset Explorer", "path": "/builder/dataset-explorer"},
            {"key": "pipeline-studio", "label": "Pipeline Studio", "path": "/builder/pipelines"},
            {"key": "metric-builder", "label": "Metric Builder", "path": "/builder/metric-builder"},
            {"key": "dashboard-builder", "label": "Dashboard Builder", "path": "/builder/dashboard-builder"},
            {"key": "ad-hoc-report", "label": "Ad-Hoc Report Builder", "path": "/builder/ad-hoc-report"},
            {"key": "forecasting", "label": "Forecasting Studio", "path": "/builder/forecasts"},
            {"key": "alerts", "label": "Alerts", "path": "/builder/alerts"},
            {"key": "scheduler", "label": "Scheduler", "path": "/builder/scheduler"},
            {"key": "model-registry", "label": "Model Registry", "path": "/builder/model-registry"},
            {"key": "publish-center", "label": "Publish Center", "path": "/builder/publish-center"},
        ]
        # ML Owner ve Forecasting Studio + Alerts.
        if user.role == Role.ML_OWNER.value:
            builder_items = [
                i for i in builder_items
                if i["key"] in {"forecasting", "alerts", "model-registry", "dataset-explorer"}
            ]
        # Finance/Operations Owner: foco em Dashboard Builder + Publish Center + Alerts.
        if user.role in {Role.FINANCE_OWNER.value, Role.OPERATIONS_OWNER.value}:
            builder_items = [
                i for i in builder_items
                if i["key"] in {"dashboard-builder", "publish-center", "dataset-explorer", "alerts"}
            ]

    business_items: list[dict] = []
    if can_view_business_portal(user):
        all_business = [
            {"key": "operations", "label": "Operations", "path": "/business/operations",
             "area": BusinessArea.OPERATIONS.value},
            {"key": "finance", "label": "Finance", "path": "/business/finance",
             "area": BusinessArea.FINANCE.value},
            {"key": "supplier", "label": "Supplier", "path": "/business/supplier",
             "area": BusinessArea.SUPPLIER.value},
            {"key": "sales", "label": "Sales", "path": "/business/sales",
             "area": BusinessArea.SALES.value},
            {"key": "latam-executive", "label": "LATAM Executive", "path": "/business/latam-executive",
             "area": BusinessArea.LATAM_EXECUTIVE.value},
        ]
        allowed_areas = ROLE_BUSINESS_AREAS.get(user.role)
        if allowed_areas is None:
            business_items = all_business
        else:
            business_items = [i for i in all_business if i["area"] in allowed_areas]

    admin_items: list[dict] = []
    if can_access_admin(user):
        admin_items = [
            {"key": "users", "label": "Users", "path": "/admin/users"},
            {"key": "workspaces", "label": "Workspaces", "path": "/admin/workspaces"},
            {"key": "permissions", "label": "Permissions", "path": "/admin/permissions"},
            {"key": "audit-logs", "label": "Audit Logs", "path": "/admin/audit-logs"},
            {"key": "system-jobs", "label": "System Jobs", "path": "/admin/system-jobs"},
        ]

    return {
        "builder_studio": {
            "visible": bool(builder_items),
            "items": builder_items,
        },
        "business_portal": {
            "visible": bool(business_items),
            "items": business_items,
        },
        "admin": {
            "visible": bool(admin_items),
            "items": admin_items,
        },
        "workspaces": accessible_workspaces(user, ALL_WORKSPACES),
        "business_areas": accessible_business_areas(user, ALL_BUSINESS_AREAS),
    }


def build_user_permissions(user) -> dict:
    """Snapshot de booleans usado pelo frontend para esconder botões/áreas."""
    return {
        "view_builder_studio": can_view_builder_studio(user),
        "view_business_portal": can_view_business_portal(user),
        "view_admin": can_access_admin(user),
        "view_datasets": can_view_datasets(user),
        "view_data_sources": can_view_data_sources(user),
        "view_metrics": has_capability(user, "view_metrics"),
        "view_dashboards": has_capability(user, "view_dashboards"),
        "upload_dataset": has_capability(user, "upload_dataset"),
        "create_data_source": has_capability(user, "create_data_source"),
        "certify_dataset": has_capability(user, "certify_dataset"),
        "create_etl": has_capability(user, "create_etl"),
        "create_metric": has_capability(user, "create_metric"),
        "create_dashboard": has_capability(user, "create_dashboard"),
        "create_report": has_capability(user, "create_report"),
        "run_forecast": can_run_forecast(user),
        "export_data": can_export_data(user),
        "submit_for_approval": can_submit_for_approval(user),
        "publish_any": has_capability(user, "publish_any"),
        "publish_finance": has_capability(user, "publish_finance"),
        "publish_operations": has_capability(user, "publish_operations"),
        "publish_forecast": has_capability(user, "publish_forecast"),
        "schedule_job": has_capability(user, "schedule_job"),
        "view_pipelines": has_capability(user, "view_pipelines"),
        "create_pipeline": has_capability(user, "create_pipeline"),
        "run_pipeline": has_capability(user, "run_pipeline"),
        "publish_pipeline": has_capability(user, "publish_pipeline"),
        "view_forecasts": has_capability(user, "view_forecasts"),
        "create_forecast": has_capability(user, "create_forecast"),
        "view_alerts": has_capability(user, "view_alerts"),
        "create_alert": has_capability(user, "create_alert"),
        "manage_alerts": has_capability(user, "manage_alerts"),
        "manage_users": has_capability(user, "manage_users"),
        "manage_workspaces": has_capability(user, "manage_workspaces"),
        "manage_permissions": has_capability(user, "manage_permissions"),
        "view_audit_logs": has_capability(user, "view_audit_logs"),
        "view_lineage": has_capability(user, "view_lineage"),
        "run_quality_checks": has_capability(user, "run_quality_checks"),
        "export_dashboard": has_capability(user, "export_dashboard"),
        "view_model_registry": has_capability(user, "view_model_registry"),
        "register_model": has_capability(user, "register_model"),
        "capabilities": sorted(_caps(user.role)),
    }


def export_permissions_matrix() -> dict:
    """Exporta matriz RBAC para o Admin panel."""
    all_caps = sorted({c for caps in ROLE_CAPABILITIES.values() for c in caps})
    roles = [r.value for r in Role]
    matrix = {role: sorted(ROLE_CAPABILITIES.get(role, set())) for role in roles}
    workspace_access = {
        role: sorted(ws) if ws is not None else None
        for role, ws in ROLE_WORKSPACE_ACCESS.items()
    }
    business_areas = {
        role: sorted(areas) if areas is not None else None
        for role, areas in ROLE_BUSINESS_AREAS.items()
    }
    return {
        "roles": roles,
        "capabilities": all_caps,
        "matrix": matrix,
        "workspace_access": workspace_access,
        "business_areas": business_areas,
    }
