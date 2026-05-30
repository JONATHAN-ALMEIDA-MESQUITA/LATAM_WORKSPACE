"""Router de Dashboard.

CRUD do dashboard + widgets, fluxo de publicação e preview de widgets.

    GET    /dashboards                    lista (filtra por workspace acessível + status opcional)
    POST   /dashboards                    cria (Draft)
    GET    /dashboards/{id}               detalhe (com widgets)
    PUT    /dashboards/{id}               atualiza metadata
    DELETE /dashboards/{id}               remove

    POST   /dashboards/{id}/widgets       cria widget
    PUT    /dashboards/{id}/widgets/{wid} atualiza widget
    DELETE /dashboards/{id}/widgets/{wid} remove widget

    POST   /dashboards/{id}/render        renderiza todos os widgets para visualização
    POST   /dashboards/widgets/preview    renderiza UM widget ad-hoc (Dashboard Builder)

    POST   /dashboards/{id}/submit        Draft -> Pending Approval
    POST   /dashboards/{id}/publish       Pending Approval -> Published (RBAC por área)
    POST   /dashboards/{id}/archive       Published -> Archived
    POST   /dashboards/{id}/reject        Pending Approval -> Draft (rejeita pendente)

    GET    /dashboards/published          lista publicados acessíveis (para Business Portal)
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.dashboard import Dashboard, DashboardStatus, DashboardWidget, WidgetType
from app.models.dataset import Dataset
from app.models.metric import Metric
from app.models.user import User
from app.models.workspace import BusinessArea
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardOut,
    DashboardSummary,
    DashboardUpdate,
    PublishActionRequest,
    WidgetCreate,
    WidgetOut,
    WidgetPreviewRequest,
    WidgetPreviewResponse,
    WidgetUpdate,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.dashboard_engine import DashboardEngineError, render_widget
from app.services.dashboard_pdf_service import build_dashboard_pdf
from app.services.permission_service import (
    accessible_workspaces,
    can_publish_dashboard,
    can_view_business_area,
    has_capability,
)
from database import get_db


router = APIRouter(prefix="/dashboards", tags=["dashboards"])


VALID_WIDGET_TYPES = {w.value for w in WidgetType}


# ---------------------------------------------------------------------------
# Conversores                                                                
# ---------------------------------------------------------------------------

def _widget_to_out(w: DashboardWidget) -> WidgetOut:
    return WidgetOut(
        id=w.id,
        dashboard_id=w.dashboard_id,
        title=w.title,
        widget_type=w.widget_type,
        layout=w.layout_dict(),
        config=w.config_dict(),
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


def _to_summary(d: Dashboard) -> DashboardSummary:
    return DashboardSummary(
        id=d.id,
        name=d.name,
        description=d.description,
        workspace=d.workspace,
        business_area=d.business_area,
        status=d.status,
        theme=d.theme,
        created_by=d.created_by,
        created_at=d.created_at,
        updated_at=d.updated_at,
        widget_count=len(d.widgets),
    )


def _to_out(d: Dashboard) -> DashboardOut:
    return DashboardOut(
        id=d.id,
        name=d.name,
        description=d.description,
        workspace=d.workspace,
        business_area=d.business_area,
        status=d.status,
        theme=d.theme,
        created_by=d.created_by,
        created_at=d.created_at,
        updated_at=d.updated_at,
        submitted_by=d.submitted_by,
        submitted_at=d.submitted_at,
        published_by=d.published_by,
        published_at=d.published_at,
        archived_by=d.archived_by,
        archived_at=d.archived_at,
        widget_count=len(d.widgets),
        widgets=[_widget_to_out(w) for w in d.widgets],
    )


def _check_workspace(user: User, workspace: str) -> None:
    if workspace not in accessible_workspaces(user, [workspace]):
        raise HTTPException(
            status_code=403,
            detail=f"Sem acesso ao workspace {workspace}",
        )


def _resolve_dashboard(db: Session, user: User, dashboard_id: int) -> Dashboard:
    d = db.get(Dashboard, dashboard_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard não encontrado.")
    _check_workspace(user, d.workspace)
    return d


# ---------------------------------------------------------------------------
# Lista + CRUD                                                               
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DashboardSummary])
def list_dashboards(
    workspace: str | None = None,
    business_area: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_dashboards")),
) -> list[DashboardSummary]:
    q = db.query(Dashboard)
    if workspace:
        q = q.filter(Dashboard.workspace == workspace)
    if business_area:
        q = q.filter(Dashboard.business_area == business_area)
    if status:
        q = q.filter(Dashboard.status == status)
    items = q.order_by(Dashboard.updated_at.desc()).all()
    if items:
        allowed = set(accessible_workspaces(user, list({d.workspace for d in items})))
        items = [d for d in items if d.workspace in allowed]
    return [_to_summary(d) for d in items]


@router.get("/published", response_model=list[DashboardSummary])
def list_published(
    business_area: str | None = None,
    workspace: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_dashboards")),
) -> list[DashboardSummary]:
    """Lista dashboards publicados acessíveis ao usuário (Business Portal)."""
    q = db.query(Dashboard).filter(Dashboard.status == DashboardStatus.PUBLISHED.value)
    if workspace:
        q = q.filter(Dashboard.workspace == workspace)
    if business_area:
        q = q.filter(Dashboard.business_area == business_area)
    items = q.order_by(Dashboard.published_at.desc().nullslast()).all()

    out: list[Dashboard] = []
    for d in items:
        if not can_view_business_area(user, d.workspace, d.business_area):
            continue
        out.append(d)
    return [_to_summary(d) for d in out]


@router.post("", response_model=DashboardOut)
def create_dashboard(
    payload: DashboardCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_dashboard")),
) -> DashboardOut:
    _check_workspace(user, payload.workspace)
    d = Dashboard(
        name=payload.name,
        description=payload.description,
        workspace=payload.workspace,
        business_area=payload.business_area,
        theme=payload.theme,
        status=DashboardStatus.DRAFT.value,
        created_by=user.email,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    log_action(
        db,
        user_email=user.email,
        action="create_dashboard",
        object_type="dashboard",
        object_name=d.name,
        workspace=d.workspace,
        business_area=d.business_area,
    )
    return _to_out(d)


@router.get("/{dashboard_id}", response_model=DashboardOut)
def get_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_dashboards")),
) -> DashboardOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    return _to_out(d)


@router.put("/{dashboard_id}", response_model=DashboardOut)
def update_dashboard(
    dashboard_id: int,
    payload: DashboardUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_dashboard")),
) -> DashboardOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    if d.created_by != user.email and not has_capability(user, "publish_any"):
        raise HTTPException(
            status_code=403, detail="Apenas o owner ou admin pode editar este dashboard."
        )
    if payload.name is not None:
        d.name = payload.name
    if payload.description is not None:
        d.description = payload.description
    if payload.workspace is not None:
        _check_workspace(user, payload.workspace)
        d.workspace = payload.workspace
    if payload.business_area is not None:
        d.business_area = payload.business_area
    if payload.theme is not None:
        d.theme = payload.theme
    db.commit()
    db.refresh(d)
    return _to_out(d)


@router.delete("/{dashboard_id}")
def delete_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_dashboard")),
) -> dict:
    d = _resolve_dashboard(db, user, dashboard_id)
    if d.created_by != user.email and not has_capability(user, "publish_any"):
        raise HTTPException(status_code=403, detail="Sem permissão para remover.")
    name = d.name
    workspace = d.workspace
    business_area = d.business_area
    db.delete(d)
    db.commit()
    log_action(
        db,
        user_email=user.email,
        action="delete_dashboard",
        object_type="dashboard",
        object_name=name,
        workspace=workspace,
        business_area=business_area,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Widgets                                                                    
# ---------------------------------------------------------------------------

@router.post("/{dashboard_id}/widgets", response_model=WidgetOut)
def create_widget(
    dashboard_id: int,
    payload: WidgetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_dashboard")),
) -> WidgetOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    if payload.widget_type not in VALID_WIDGET_TYPES:
        raise HTTPException(status_code=400, detail=f"widget_type inválido: {payload.widget_type}")

    w = DashboardWidget(
        dashboard_id=d.id,
        title=payload.title,
        widget_type=payload.widget_type,
        layout=json.dumps(payload.layout.model_dump()),
        config=json.dumps(payload.config or {}),
    )
    db.add(w)
    d.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(w)
    return _widget_to_out(w)


@router.put("/{dashboard_id}/widgets/{widget_id}", response_model=WidgetOut)
def update_widget(
    dashboard_id: int,
    widget_id: int,
    payload: WidgetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_dashboard")),
) -> WidgetOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    w = db.get(DashboardWidget, widget_id)
    if not w or w.dashboard_id != d.id:
        raise HTTPException(status_code=404, detail="Widget não encontrado.")

    if payload.title is not None:
        w.title = payload.title
    if payload.widget_type is not None:
        if payload.widget_type not in VALID_WIDGET_TYPES:
            raise HTTPException(status_code=400, detail=f"widget_type inválido: {payload.widget_type}")
        w.widget_type = payload.widget_type
    if payload.layout is not None:
        w.layout = json.dumps(payload.layout.model_dump())
    if payload.config is not None:
        w.config = json.dumps(payload.config)
    d.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(w)
    return _widget_to_out(w)


@router.delete("/{dashboard_id}/widgets/{widget_id}")
def delete_widget(
    dashboard_id: int,
    widget_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_dashboard")),
) -> dict:
    d = _resolve_dashboard(db, user, dashboard_id)
    w = db.get(DashboardWidget, widget_id)
    if not w or w.dashboard_id != d.id:
        raise HTTPException(status_code=404, detail="Widget não encontrado.")
    db.delete(w)
    d.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Render / Preview                                                           
# ---------------------------------------------------------------------------

def _make_dataset_resolver(db: Session, user: User):
    def _resolve(dataset_id: int):
        ds = db.get(Dataset, dataset_id)
        if not ds:
            return None
        if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
            return None
        return ds
    return _resolve


def _make_metric_resolver(db: Session, user: User):
    def _resolve(metric_id: int):
        m = db.get(Metric, metric_id)
        if not m:
            return None
        if m.workspace not in accessible_workspaces(user, [m.workspace]):
            return None
        return m
    return _resolve


@router.post("/widgets/preview", response_model=WidgetPreviewResponse)
def preview_widget_inline(
    payload: WidgetPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_dashboards")),
) -> WidgetPreviewResponse:
    try:
        result = render_widget(
            widget_type=payload.widget_type,
            config=payload.config or {},
            title=(payload.config or {}).get("title", ""),
            dataset_resolver=_make_dataset_resolver(db, user),
            metric_resolver=_make_metric_resolver(db, user),
        )
    except DashboardEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WidgetPreviewResponse(**result)


@router.post("/{dashboard_id}/render", response_model=list[WidgetPreviewResponse])
def render_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_dashboards")),
) -> list[WidgetPreviewResponse]:
    """Renderiza todos os widgets do dashboard (usado pelo Business Portal e pelo viewer)."""
    d = _resolve_dashboard(db, user, dashboard_id)
    dataset_resolver = _make_dataset_resolver(db, user)
    metric_resolver = _make_metric_resolver(db, user)
    out: list[WidgetPreviewResponse] = []
    for w in d.widgets:
        try:
            result = render_widget(
                widget_type=w.widget_type,
                config=w.config_dict(),
                title=w.title,
                dataset_resolver=dataset_resolver,
                metric_resolver=metric_resolver,
            )
        except DashboardEngineError as exc:
            result = {
                "widget_type": w.widget_type,
                "title": w.title,
                "kpi": None,
                "chart": None,
                "table": None,
                "text": None,
                "rows_used": 0,
                "notes": f"Erro ao renderizar widget: {exc}",
            }
        result["widget_id"] = w.id
        result["layout"] = w.layout_dict()
        out.append(WidgetPreviewResponse(**result))
    return out


@router.post("/{dashboard_id}/export-pdf")
def export_dashboard_pdf(
    dashboard_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("export_dashboard")),
):
    """Exporta dashboard renderizado como PDF (demo Phase 9)."""
    d = _resolve_dashboard(db, user, dashboard_id)
    dataset_resolver = _make_dataset_resolver(db, user)
    metric_resolver = _make_metric_resolver(db, user)
    rendered: list[dict] = []
    for w in d.widgets:
        try:
            result = render_widget(
                widget_type=w.widget_type,
                config=w.config_dict(),
                title=w.title,
                dataset_resolver=dataset_resolver,
                metric_resolver=metric_resolver,
            )
        except DashboardEngineError as exc:
            result = {"title": w.title, "widget_type": w.widget_type, "notes": str(exc)}
        rendered.append(result)
    pdf_bytes = build_dashboard_pdf(d, rendered)
    filename = f"dashboard_{d.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    log_action(
        db,
        user_email=user.email,
        action="export_dashboard_pdf",
        object_type="dashboard",
        object_name=d.name,
        workspace=d.workspace,
        business_area=d.business_area,
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Publish flow                                                               
# ---------------------------------------------------------------------------

@router.post("/{dashboard_id}/submit", response_model=DashboardOut)
def submit_for_approval(
    dashboard_id: int,
    payload: PublishActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("submit_for_approval")),
) -> DashboardOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    if d.status not in {DashboardStatus.DRAFT.value, DashboardStatus.ARCHIVED.value}:
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível submeter um dashboard com status '{d.status}'.",
        )
    if len(d.widgets) == 0:
        raise HTTPException(status_code=400, detail="Dashboard precisa ter ao menos 1 widget.")

    d.status = DashboardStatus.PENDING_APPROVAL.value
    d.submitted_by = user.email
    d.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(d)
    log_action(
        db,
        user_email=user.email,
        action="submit_for_approval",
        object_type="dashboard",
        object_name=d.name,
        workspace=d.workspace,
        business_area=d.business_area,
        details=(payload.comment if payload else ""),
    )
    return _to_out(d)


@router.post("/{dashboard_id}/publish", response_model=DashboardOut)
def publish_dashboard(
    dashboard_id: int,
    payload: PublishActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    if not can_publish_dashboard(user, d.workspace, d.business_area):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Sem permissão para publicar dashboards em "
                f"workspace={d.workspace} area={d.business_area}"
            ),
        )
    if d.status not in {
        DashboardStatus.DRAFT.value,
        DashboardStatus.PENDING_APPROVAL.value,
        DashboardStatus.ARCHIVED.value,
    }:
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível publicar com status '{d.status}'.",
        )

    d.status = DashboardStatus.PUBLISHED.value
    d.published_by = user.email
    d.published_at = datetime.utcnow()
    db.commit()
    db.refresh(d)
    log_action(
        db,
        user_email=user.email,
        action="publish_dashboard",
        object_type="dashboard",
        object_name=d.name,
        workspace=d.workspace,
        business_area=d.business_area,
        details=(payload.comment if payload else ""),
    )
    return _to_out(d)


@router.post("/{dashboard_id}/archive", response_model=DashboardOut)
def archive_dashboard(
    dashboard_id: int,
    payload: PublishActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    if d.created_by != user.email and not can_publish_dashboard(user, d.workspace, d.business_area):
        raise HTTPException(status_code=403, detail="Sem permissão para arquivar.")
    d.status = DashboardStatus.ARCHIVED.value
    d.archived_by = user.email
    d.archived_at = datetime.utcnow()
    db.commit()
    db.refresh(d)
    log_action(
        db,
        user_email=user.email,
        action="archive_dashboard",
        object_type="dashboard",
        object_name=d.name,
        workspace=d.workspace,
        business_area=d.business_area,
        details=(payload.comment if payload else ""),
    )
    return _to_out(d)


@router.post("/{dashboard_id}/reject", response_model=DashboardOut)
def reject_pending(
    dashboard_id: int,
    payload: PublishActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardOut:
    d = _resolve_dashboard(db, user, dashboard_id)
    if not can_publish_dashboard(user, d.workspace, d.business_area):
        raise HTTPException(status_code=403, detail="Sem permissão para rejeitar.")
    if d.status != DashboardStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=400, detail="Dashboard não está pendente.")
    d.status = DashboardStatus.DRAFT.value
    db.commit()
    db.refresh(d)
    log_action(
        db,
        user_email=user.email,
        action="reject_dashboard",
        object_type="dashboard",
        object_name=d.name,
        workspace=d.workspace,
        business_area=d.business_area,
        details=(payload.comment if payload else ""),
    )
    return _to_out(d)
