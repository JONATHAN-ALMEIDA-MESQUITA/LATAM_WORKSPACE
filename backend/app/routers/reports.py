"""Router Ad-Hoc Report Builder (Phase 7).

    POST   /reports/preview              preview SQL (limitado)
    POST   /reports/export-csv           export CSV
    GET    /reports/examples             templates de query
    POST   /reports/save-dataset         grava resultado como Dataset

    GET    /reports/saved                lista queries salvas
    POST   /reports/saved                cria query salva
    GET    /reports/saved/{id}           detalhe
    PUT    /reports/saved/{id}           atualiza
    DELETE /reports/saved/{id}           remove
    POST   /reports/saved/{id}/run       executa query salva (preview)
"""

from __future__ import annotations

import csv
import io
import math
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetColumn, DatasetSourceType, DatasetStatus
from app.models.report import SavedReport
from app.models.user import User
from app.schemas.report import (
    JoinSuggestion,
    ReportExportRequest,
    ReportPreviewRequest,
    ReportPreviewResponse,
    ReportSaveDatasetRequest,
    SavedReportCreate,
    SavedReportOut,
    SavedReportUpdate,
    VisualReportRequest,
)
from app.services.ad_hoc_engine import AdHocQueryError, run_query, run_query_dataframe
from app.services.visual_report_engine import (
    allowed_column_set,
    build_table_refs,
    build_visual_sql,
    example_queries_multi,
    friendly_alias,
    run_query_tables,
    run_query_tables_dataframe,
    suggest_joins,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.permission_service import accessible_workspaces
from app.utils.file_utils import save_parquet
from config import settings
from database import get_db


router = APIRouter(prefix="/reports", tags=["reports"])


def _check_workspace(user: User, workspace: str) -> None:
    if workspace not in accessible_workspaces(user, [workspace]):
        raise HTTPException(status_code=403, detail=f"Sem acesso ao workspace {workspace}")


def _resolve_dataset(db: Session, user: User, dataset_id: int) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset nao encontrado.")
    _check_workspace(user, ds.workspace)
    return ds


def _to_saved_out(db: Session, r: SavedReport) -> SavedReportOut:
    src = db.get(Dataset, r.source_dataset_id)
    return SavedReportOut(
        id=r.id,
        name=r.name,
        description=r.description,
        workspace=r.workspace,
        business_area=r.business_area,
        source_dataset_id=r.source_dataset_id,
        sql_query=r.sql_query,
        created_by=r.created_by,
        created_at=r.created_at,
        updated_at=r.updated_at,
        last_run_at=r.last_run_at,
        source_dataset_name=src.name if src else None,
    )


def _persist_report_dataset(
    db: Session,
    *,
    df: pd.DataFrame,
    name: str,
    description: str,
    workspace: str,
    business_area: str,
    created_by: str,
) -> Dataset:
    from app.services.profiling_service import profile_dataframe, serialize_sample_values

    ds = Dataset(
        name=name,
        description=description,
        workspace=workspace,
        business_area=business_area,
        source_type=DatasetSourceType.REPORT_OUTPUT.value,
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
        status=DatasetStatus.VALIDATED.value,
        created_by=created_by,
    )
    db.add(ds)
    db.flush()

    processed_path = (settings.processed_dir / f"dataset_{ds.id}.parquet").resolve()
    save_parquet(df, processed_path)
    ds.processed_path = str(processed_path)

    profiles = profile_dataframe(df)
    for idx, prof in enumerate(profiles):
        db.add(
            DatasetColumn(
                dataset_id=ds.id,
                position=idx,
                name=prof.name,
                dtype=prof.dtype,
                null_count=prof.null_count,
                distinct_count=prof.distinct_count,
                min_value=prof.min_value,
                max_value=prof.max_value,
                mean_value=(
                    prof.mean_value
                    if prof.mean_value is not None
                    and not (isinstance(prof.mean_value, float) and math.isnan(prof.mean_value))
                    else None
                ),
                std_value=(
                    prof.std_value
                    if prof.std_value is not None
                    and not (isinstance(prof.std_value, float) and math.isnan(prof.std_value))
                    else None
                ),
                sample_values=serialize_sample_values(prof.sample_values),
            )
        )
    db.flush()
    return ds


def _resolve_extra_datasets(
    db: Session,
    user: User,
    primary: Dataset,
    extras: list,
) -> list[tuple[Dataset, str | None]]:
    out: list[tuple[Dataset, str | None]] = []
    for ref in extras:
        ds = _resolve_dataset(db, user, ref.dataset_id)
        if ds.id == primary.id:
            continue
        out.append((ds, ref.alias))
    return out


def _table_refs_for_request(
    db: Session,
    user: User,
    primary_id: int,
    extras: list,
):
    primary = _resolve_dataset(db, user, primary_id)
    extra_pairs = _resolve_extra_datasets(db, user, primary, extras)
    return primary, build_table_refs(primary, extra_pairs)


def _column_profiles(db: Session, tables) -> dict[str, list[str]]:
    from app.models.dataset import DatasetColumn

    profiles: dict[str, list[str]] = {}
    for t in tables:
        cols = (
            db.query(DatasetColumn.name)
            .filter(DatasetColumn.dataset_id == t.dataset.id)
            .order_by(DatasetColumn.position)
            .all()
        )
        profiles[t.alias] = [c[0] for c in cols]
    return profiles


def _preview_response(result, sql: str | None = None) -> ReportPreviewResponse:
    return ReportPreviewResponse(
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        notes=result.notes,
        generated_sql=sql,
    )


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------

@router.get("/examples")
def list_examples(
    dataset_id: int | None = None,
    extra_dataset_ids: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> list[dict[str, str]]:
    if not dataset_id:
        return example_queries_multi("sales_latam", ["client_master", "product_catalog"])
    primary = _resolve_dataset(db, user, dataset_id)
    extra_names: list[str] = []
    if extra_dataset_ids:
        for part in extra_dataset_ids.split(","):
            part = part.strip()
            if part.isdigit():
                ds = _resolve_dataset(db, user, int(part))
                if ds.id != primary.id:
                    extra_names.append(ds.name)
    return example_queries_multi(primary.name, extra_names)


@router.get("/join-suggestions", response_model=list[JoinSuggestion])
def join_suggestions(
    dataset_ids: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> list[JoinSuggestion]:
    names: list[str] = []
    for part in dataset_ids.split(","):
        part = part.strip()
        if part.isdigit():
            ds = _resolve_dataset(db, user, int(part))
            names.append(ds.name)
    raw = suggest_joins(names)
    return [JoinSuggestion(**j) for j in raw]


@router.post("/preview", response_model=ReportPreviewResponse)
def preview_query(
    body: ReportPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> ReportPreviewResponse:
    primary, tables = _table_refs_for_request(
        db, user, body.dataset_id, body.extra_datasets
    )
    try:
        if len(tables) > 1 or body.extra_datasets:
            result = run_query_tables(tables, body.sql, limit=body.limit)
        else:
            result = run_query(primary, body.sql, limit=body.limit)
    except AdHocQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _preview_response(result, body.sql)


@router.post("/visual-preview", response_model=ReportPreviewResponse)
def visual_preview(
    body: VisualReportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> ReportPreviewResponse:
    extras = []
    join_ds = None
    if body.join:
        join_ds = _resolve_dataset(db, user, body.join.dataset_id)
        from app.schemas.report import ExtraDatasetRef

        extras = [ExtraDatasetRef(dataset_id=join_ds.id, alias=body.join.alias)]

    primary, tables = _table_refs_for_request(
        db, user, body.primary_dataset_id, extras
    )
    profiles = _column_profiles(db, tables)
    allowed = allowed_column_set(tables, profiles)
    primary_alias = friendly_alias(primary, "sales")

    join_cfg = None
    if body.join and join_ds:
        right_alias = body.join.alias or friendly_alias(join_ds)
        join_cfg = {
            "alias": right_alias,
            "left_column": body.join.left_column,
            "right_column": body.join.right_column,
            "join_type": body.join.join_type,
        }

    try:
        sql = build_visual_sql(
            primary_alias=primary_alias,
            join=join_cfg,
            columns=[c.model_dump() for c in body.columns],
            filters=[f.model_dump() for f in body.filters],
            group_by=[g.model_dump() for g in body.group_by],
            metrics=[m.model_dump() for m in body.metrics],
            order_by=body.order_by.model_dump() if body.order_by else None,
            order_dir=body.order_dir,
            limit=body.limit,
            allowed_columns=allowed,
        )
        result = run_query_tables(tables, sql, limit=body.limit)
    except AdHocQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _preview_response(result, sql)


@router.post("/export-csv")
def export_csv(
    body: ReportExportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_report")),
) -> StreamingResponse:
    primary, tables = _table_refs_for_request(
        db, user, body.dataset_id, body.extra_datasets
    )
    try:
        if len(tables) > 1 or body.extra_datasets:
            df = run_query_tables_dataframe(tables, body.sql, limit=body.limit)
        else:
            df = run_query_dataframe(primary, body.sql, limit=body.limit)
    except AdHocQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    buf = io.StringIO()
    df.to_csv(buf, index=False, quoting=csv.QUOTE_MINIMAL)
    buf.seek(0)
    filename = f"report_{primary.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    log_action(
        db,
        user_email=user.email,
        action="report_export_csv",
        object_type="dataset",
        object_name=primary.name,
        workspace=primary.workspace,
        details=f"rows={len(df)} limit={body.limit}",
    )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/save-dataset")
def save_as_dataset(
    body: ReportSaveDatasetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_report")),
) -> dict:
    primary, tables = _table_refs_for_request(
        db, user, body.dataset_id, body.extra_datasets
    )
    _check_workspace(user, body.workspace)
    try:
        if len(tables) > 1 or body.extra_datasets:
            df = run_query_tables_dataframe(tables, body.sql, limit=None)
        else:
            df = run_query_dataframe(primary, body.sql, limit=None)
    except AdHocQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_ds = _persist_report_dataset(
        db,
        df=df,
        name=body.output_name,
        description=body.description or f"Ad-hoc report from dataset '{primary.name}'",
        workspace=body.workspace,
        business_area=body.business_area or primary.business_area,
        created_by=user.email,
    )
    log_action(
        db,
        user_email=user.email,
        action="report_save_dataset",
        object_type="dataset",
        object_name=new_ds.name,
        workspace=new_ds.workspace,
        details=f"source_dataset_id={primary.id} rows={len(df)}",
    )
    return {"dataset_id": new_ds.id, "name": new_ds.name, "row_count": new_ds.row_count}


# ---------------------------------------------------------------------------
# Saved reports CRUD
# ---------------------------------------------------------------------------

@router.get("/saved", response_model=list[SavedReportOut])
def list_saved(
    workspace: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> list[SavedReportOut]:
    items = db.query(SavedReport).order_by(SavedReport.updated_at.desc()).all()
    if workspace:
        _check_workspace(user, workspace)
        items = [r for r in items if r.workspace == workspace]
    else:
        allowed = set(accessible_workspaces(user, list({r.workspace for r in items})))
        if allowed:
            items = [r for r in items if r.workspace in allowed]
        else:
            items = []
    return [_to_saved_out(db, r) for r in items]


@router.post("/saved", response_model=SavedReportOut)
def create_saved(
    body: SavedReportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_report")),
) -> SavedReportOut:
    _check_workspace(user, body.workspace)
    _resolve_dataset(db, user, body.source_dataset_id)
    r = SavedReport(
        name=body.name,
        description=body.description,
        workspace=body.workspace,
        business_area=body.business_area,
        source_dataset_id=body.source_dataset_id,
        sql_query=body.sql_query,
        created_by=user.email,
    )
    db.add(r)
    db.flush()
    log_action(
        db,
        user_email=user.email,
        action="saved_report_create",
        object_type="saved_report",
        object_name=r.name,
        workspace=r.workspace,
        details=f"source_dataset_id={r.source_dataset_id}",
    )
    return _to_saved_out(db, r)


@router.get("/saved/{report_id}", response_model=SavedReportOut)
def get_saved(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> SavedReportOut:
    r = db.get(SavedReport, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Relatorio salvo nao encontrado.")
    _check_workspace(user, r.workspace)
    return _to_saved_out(db, r)


@router.put("/saved/{report_id}", response_model=SavedReportOut)
def update_saved(
    report_id: int,
    body: SavedReportUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_report")),
) -> SavedReportOut:
    r = db.get(SavedReport, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Relatorio salvo nao encontrado.")
    _check_workspace(user, r.workspace)
    data = body.model_dump(exclude_unset=True)
    if "workspace" in data and data["workspace"]:
        _check_workspace(user, data["workspace"])
    if "source_dataset_id" in data and data["source_dataset_id"]:
        _resolve_dataset(db, user, data["source_dataset_id"])
    for k, v in data.items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return _to_saved_out(db, r)


@router.delete("/saved/{report_id}")
def delete_saved(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_report")),
) -> dict:
    r = db.get(SavedReport, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Relatorio salvo nao encontrado.")
    _check_workspace(user, r.workspace)
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.post("/saved/{report_id}/run", response_model=ReportPreviewResponse)
def run_saved(
    report_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> ReportPreviewResponse:
    r = db.get(SavedReport, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Relatorio salvo nao encontrado.")
    _check_workspace(user, r.workspace)
    ds = _resolve_dataset(db, user, r.source_dataset_id)
    try:
        result = run_query(ds, r.sql_query, limit=min(limit, 5000))
    except AdHocQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    r.last_run_at = datetime.utcnow()
    db.commit()
    return ReportPreviewResponse(
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        notes=result.notes,
    )
