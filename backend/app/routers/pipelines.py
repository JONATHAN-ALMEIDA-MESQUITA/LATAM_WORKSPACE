"""Router de Pipelines (ETL Builder - Phase 3b).

    GET    /pipelines                       lista
    POST   /pipelines                       cria (Draft)
    GET    /pipelines/{id}                  detalhe (com steps)
    PUT    /pipelines/{id}                  atualiza metadata
    DELETE /pipelines/{id}                  remove

    POST   /pipelines/{id}/steps            cria step (append no final)
    PUT    /pipelines/{id}/steps/{sid}      atualiza step
    DELETE /pipelines/{id}/steps/{sid}      remove step
    POST   /pipelines/{id}/steps/reorder    reordena (lista de step_ids)

    POST   /pipelines/preview               preview ad-hoc (steps no payload)
    POST   /pipelines/{id}/preview          preview do pipeline ja salvo

    POST   /pipelines/{id}/run              executa pipeline (cria PipelineRun)
    GET    /pipelines/{id}/runs             historico de execucoes

    POST   /pipelines/{id}/publish          Draft -> Published
    POST   /pipelines/{id}/archive          Published -> Archived
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.pipeline import (
    Pipeline,
    PipelineRun,
    PipelineStatus,
    PipelineStep,
    RunStatus,
    StepType,
)
from app.models.user import User
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineOut,
    PipelineSummary,
    PipelineUpdate,
    PreviewRequest,
    PreviewResponse,
    PublishActionRequest,
    RunOut,
    RunRequest,
    StepCreate,
    StepOut,
    StepUpdate,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.permission_service import (
    accessible_workspaces,
    can_publish_pipeline,
    can_run_pipeline,
    has_capability,
)
from app.services.pipeline_engine import PipelineError, StepFailure, execute, preview
from database import get_db


router = APIRouter(prefix="/pipelines", tags=["pipelines"])


VALID_STEP_TYPES = {s.value for s in StepType}


# ---------------------------------------------------------------------------
# Conversores
# ---------------------------------------------------------------------------

def _step_to_out(s: PipelineStep) -> StepOut:
    return StepOut(
        id=s.id,
        pipeline_id=s.pipeline_id,
        order_index=s.order_index,
        name=s.name,
        step_type=s.step_type,
        config=s.config_dict(),
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _to_out(p: Pipeline) -> PipelineOut:
    return PipelineOut(
        id=p.id,
        name=p.name,
        description=p.description,
        workspace=p.workspace,
        business_area=p.business_area,
        schedule_cron=p.schedule_cron,
        status=p.status,
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
        published_by=p.published_by,
        published_at=p.published_at,
        archived_by=p.archived_by,
        archived_at=p.archived_at,
        last_run_at=p.last_run_at,
        last_run_status=p.last_run_status,
        steps=[_step_to_out(s) for s in p.steps],
    )


def _to_summary(p: Pipeline) -> PipelineSummary:
    return PipelineSummary(
        id=p.id,
        name=p.name,
        description=p.description,
        workspace=p.workspace,
        business_area=p.business_area,
        schedule_cron=p.schedule_cron,
        status=p.status,
        created_by=p.created_by,
        updated_at=p.updated_at,
        last_run_at=p.last_run_at,
        last_run_status=p.last_run_status,
        step_count=len(p.steps),
    )


def _run_to_out(r: PipelineRun) -> RunOut:
    return RunOut(
        id=r.id,
        pipeline_id=r.pipeline_id,
        triggered_by=r.triggered_by,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
        duration_ms=r.duration_ms,
        rows_in=r.rows_in,
        rows_out=r.rows_out,
        target_dataset_id=r.target_dataset_id,
        error_message=r.error_message,
        failed_step_index=r.failed_step_index,
        failed_step_name=r.failed_step_name,
        failed_step_type=r.failed_step_type,
        logs=r.logs,
    )


def _check_workspace(user: User, workspace: str) -> None:
    if workspace not in accessible_workspaces(user, [workspace]):
        raise HTTPException(
            status_code=403,
            detail=f"Sem acesso ao workspace {workspace}",
        )


def _resolve_pipeline(db: Session, user: User, pipeline_id: int) -> Pipeline:
    p = db.get(Pipeline, pipeline_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline nao encontrado.")
    _check_workspace(user, p.workspace)
    return p


def _validate_step_type(step_type: str) -> None:
    if step_type not in VALID_STEP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"step_type invalido: {step_type}. Validos: {sorted(VALID_STEP_TYPES)}",
        )


def _make_dataset_resolver(db: Session, user: User):
    """Cria resolver que valida workspace do dataset contra o usuario."""
    def _resolve(ds_id: int) -> Dataset | None:
        ds = db.get(Dataset, ds_id)
        if not ds:
            return None
        if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
            return None
        return ds
    return _resolve


# ---------------------------------------------------------------------------
# Lista + CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PipelineSummary])
def list_pipelines(
    workspace: str | None = None,
    business_area: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_pipelines")),
) -> list[PipelineSummary]:
    q = db.query(Pipeline)
    if workspace:
        q = q.filter(Pipeline.workspace == workspace)
    if business_area:
        q = q.filter(Pipeline.business_area == business_area)
    if status:
        q = q.filter(Pipeline.status == status)
    items = q.order_by(Pipeline.updated_at.desc()).all()
    if items:
        allowed = set(accessible_workspaces(user, list({p.workspace for p in items})))
        items = [p for p in items if p.workspace in allowed]
    return [_to_summary(p) for p in items]


@router.post("", response_model=PipelineOut)
def create_pipeline(
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_pipeline")),
) -> PipelineOut:
    _check_workspace(user, payload.workspace)
    p = Pipeline(
        name=payload.name,
        description=payload.description,
        workspace=payload.workspace,
        business_area=payload.business_area,
        schedule_cron=payload.schedule_cron,
        status=PipelineStatus.DRAFT.value,
        created_by=user.email,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    log_action(
        db,
        user_email=user.email,
        action="create_pipeline",
        object_type="pipeline",
        object_name=p.name,
        workspace=p.workspace,
        business_area=p.business_area,
    )
    return _to_out(p)


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_pipelines")),
) -> PipelineOut:
    p = _resolve_pipeline(db, user, pipeline_id)
    return _to_out(p)


@router.put("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_pipeline")),
) -> PipelineOut:
    p = _resolve_pipeline(db, user, pipeline_id)
    if p.created_by != user.email and not has_capability(user, "publish_any"):
        raise HTTPException(
            status_code=403,
            detail="Apenas o autor ou um admin pode editar este pipeline.",
        )
    data = payload.model_dump(exclude_unset=True)
    if "workspace" in data and data["workspace"]:
        _check_workspace(user, data["workspace"])
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.delete("/{pipeline_id}")
def delete_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_pipeline")),
) -> dict:
    p = _resolve_pipeline(db, user, pipeline_id)
    if p.created_by != user.email and not has_capability(user, "publish_any"):
        raise HTTPException(status_code=403, detail="Sem permissao para remover.")
    log_action(
        db,
        user_email=user.email,
        action="delete_pipeline",
        object_type="pipeline",
        object_name=p.name,
        workspace=p.workspace,
    )
    db.delete(p)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Steps CRUD
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/steps", response_model=StepOut)
def create_step(
    pipeline_id: int,
    payload: StepCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_pipeline")),
) -> StepOut:
    p = _resolve_pipeline(db, user, pipeline_id)
    _validate_step_type(payload.step_type)
    next_idx = max([s.order_index for s in p.steps], default=-1) + 1
    s = PipelineStep(
        pipeline_id=p.id,
        order_index=payload.order_index if payload.order_index > 0 else next_idx,
        name=payload.name or payload.step_type,
        step_type=payload.step_type,
        config=json.dumps(payload.config or {}),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _step_to_out(s)


@router.put("/{pipeline_id}/steps/{step_id}", response_model=StepOut)
def update_step(
    pipeline_id: int,
    step_id: int,
    payload: StepUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_pipeline")),
) -> StepOut:
    p = _resolve_pipeline(db, user, pipeline_id)
    s = db.get(PipelineStep, step_id)
    if not s or s.pipeline_id != p.id:
        raise HTTPException(status_code=404, detail="Step nao encontrado.")
    data = payload.model_dump(exclude_unset=True)
    if "step_type" in data and data["step_type"]:
        _validate_step_type(data["step_type"])
        s.step_type = data["step_type"]
    if "name" in data and data["name"] is not None:
        s.name = data["name"]
    if "order_index" in data and data["order_index"] is not None:
        s.order_index = data["order_index"]
    if "config" in data and data["config"] is not None:
        s.config = json.dumps(data["config"])
    db.commit()
    db.refresh(s)
    return _step_to_out(s)


@router.delete("/{pipeline_id}/steps/{step_id}")
def delete_step(
    pipeline_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_pipeline")),
) -> dict:
    p = _resolve_pipeline(db, user, pipeline_id)
    s = db.get(PipelineStep, step_id)
    if not s or s.pipeline_id != p.id:
        raise HTTPException(status_code=404, detail="Step nao encontrado.")
    db.delete(s)
    db.commit()
    return {"deleted": True}


class ReorderRequest(BaseModel):
    step_ids: list[int]


@router.post("/{pipeline_id}/steps/reorder", response_model=list[StepOut])
def reorder_steps(
    pipeline_id: int,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_pipeline")),
) -> list[StepOut]:
    p = _resolve_pipeline(db, user, pipeline_id)
    by_id = {s.id: s for s in p.steps}
    if set(payload.step_ids) != set(by_id.keys()):
        raise HTTPException(
            status_code=400,
            detail="step_ids precisa cobrir exatamente todos os steps do pipeline.",
        )
    for idx, sid in enumerate(payload.step_ids):
        by_id[sid].order_index = idx
    db.commit()
    p = _resolve_pipeline(db, user, pipeline_id)
    return [_step_to_out(s) for s in p.steps]


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _steps_payload_from_pipeline(p: Pipeline) -> list[dict]:
    return [
        {
            "step_type": s.step_type,
            "name": s.name,
            "config": s.config_dict(),
        }
        for s in p.steps
    ]


def _steps_payload_from_create(items: list[StepCreate]) -> list[dict]:
    return [
        {
            "step_type": s.step_type,
            "name": s.name,
            "config": s.config or {},
        }
        for s in items
    ]


@router.post("/preview", response_model=PreviewResponse)
def preview_adhoc(
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_pipelines")),
) -> PreviewResponse:
    """Preview de pipeline ad-hoc (steps direto do payload, sem salvar).

    Util pro editor de pipeline durante construcao.
    """
    if not payload.steps:
        raise HTTPException(status_code=400, detail="payload.steps e obrigatorio.")
    resolver = _make_dataset_resolver(db, user)
    try:
        data = preview(
            _steps_payload_from_create(payload.steps),
            dataset_resolver=resolver,
            up_to_index=payload.up_to_index,
            sample_rows=payload.sample_rows,
        )
    except StepFailure as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": exc.original_message,
                "failed_step_index": exc.step_index,
                "failed_step_name": exc.step_name,
                "failed_step_type": exc.step_type,
            },
        ) from exc
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PreviewResponse(**data)


@router.post("/{pipeline_id}/preview", response_model=PreviewResponse)
def preview_pipeline(
    pipeline_id: int,
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_pipelines")),
) -> PreviewResponse:
    """Preview de pipeline ja salvo (com steps do banco)."""
    p = _resolve_pipeline(db, user, pipeline_id)
    resolver = _make_dataset_resolver(db, user)
    try:
        data = preview(
            _steps_payload_from_pipeline(p),
            dataset_resolver=resolver,
            up_to_index=payload.up_to_index,
            sample_rows=payload.sample_rows,
        )
    except StepFailure as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": exc.original_message,
                "failed_step_index": exc.step_index,
                "failed_step_name": exc.step_name,
                "failed_step_type": exc.step_type,
            },
        ) from exc
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PreviewResponse(**data)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/run", response_model=RunOut)
def run_pipeline(
    pipeline_id: int,
    payload: RunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RunOut:
    p = _resolve_pipeline(db, user, pipeline_id)
    if not can_run_pipeline(user, p.workspace):
        raise HTTPException(status_code=403, detail="Sem permissao para executar pipeline.")
    if not p.steps:
        raise HTTPException(status_code=400, detail="Pipeline sem steps.")

    run = PipelineRun(
        pipeline_id=p.id,
        triggered_by=user.email,
        status=RunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    resolver = _make_dataset_resolver(db, user)
    t0 = time.perf_counter()
    try:
        result = execute(
            _steps_payload_from_pipeline(p),
            dataset_resolver=resolver,
            db=db,
            created_by=user.email,
            pipeline_id=p.id,
            persist_target=True,
        )
        run.status = RunStatus.SUCCESS.value
        run.rows_in = result.total_rows_in()
        run.rows_out = result.total_rows_out()
        run.target_dataset_id = result.target_dataset_id
        run.logs = json.dumps([log.__dict__ for log in result.logs], default=str)
    except StepFailure as exc:
        db.rollback()
        run = db.get(PipelineRun, run.id)  # recupera apos rollback
        run.status = RunStatus.FAILED.value
        run.error_message = exc.original_message
        run.failed_step_index = exc.step_index
        run.failed_step_name = exc.step_name
        run.failed_step_type = exc.step_type
    except PipelineError as exc:
        db.rollback()
        run = db.get(PipelineRun, run.id)
        run.status = RunStatus.FAILED.value
        run.error_message = str(exc)
    except Exception as exc:
        db.rollback()
        run = db.get(PipelineRun, run.id)
        run.status = RunStatus.FAILED.value
        run.error_message = f"Erro inesperado: {exc}"
    finally:
        run.finished_at = datetime.utcnow()
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        # Atualiza estado do pipeline
        p_db = db.get(Pipeline, p.id)
        p_db.last_run_at = run.finished_at
        p_db.last_run_status = run.status
        db.commit()
        db.refresh(run)

    log_action(
        db,
        user_email=user.email,
        action="run_pipeline",
        object_type="pipeline",
        object_name=p.name,
        workspace=p.workspace,
        details=f"status={run.status} rows_out={run.rows_out}",
    )

    # Trigger alerts (best-effort - falhas nao quebram o response)
    try:
        from app.services.alert_triggers import trigger_for
        trigger_for(db, target_kind="pipeline", target_id=p.id)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    return _run_to_out(run)


@router.get("/{pipeline_id}/runs", response_model=list[RunOut])
def list_runs(
    pipeline_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_pipelines")),
) -> list[RunOut]:
    p = _resolve_pipeline(db, user, pipeline_id)
    runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_id == p.id)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_run_to_out(r) for r in runs]


# ---------------------------------------------------------------------------
# Publish flow
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/publish", response_model=PipelineOut)
def publish(
    pipeline_id: int,
    payload: PublishActionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PipelineOut:
    p = _resolve_pipeline(db, user, pipeline_id)
    if not can_publish_pipeline(user, p.workspace):
        raise HTTPException(status_code=403, detail="Sem permissao para publicar pipeline.")
    if p.status == PipelineStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="Pipeline ja esta publicado.")
    p.status = PipelineStatus.PUBLISHED.value
    p.published_by = user.email
    p.published_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    log_action(
        db,
        user_email=user.email,
        action="publish_pipeline",
        object_type="pipeline",
        object_name=p.name,
        workspace=p.workspace,
        details=payload.note or "",
    )
    return _to_out(p)


@router.post("/{pipeline_id}/archive", response_model=PipelineOut)
def archive(
    pipeline_id: int,
    payload: PublishActionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PipelineOut:
    p = _resolve_pipeline(db, user, pipeline_id)
    if not can_publish_pipeline(user, p.workspace) and p.created_by != user.email:
        raise HTTPException(status_code=403, detail="Sem permissao para arquivar.")
    p.status = PipelineStatus.ARCHIVED.value
    p.archived_by = user.email
    p.archived_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    log_action(
        db,
        user_email=user.email,
        action="archive_pipeline",
        object_type="pipeline",
        object_name=p.name,
        workspace=p.workspace,
    )
    return _to_out(p)
