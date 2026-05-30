"""Router de Datasets.

Endpoints:
    GET    /datasets                 lista datasets acessíveis ao usuário
    POST   /datasets/upload          upload CSV/XLSX + profiling automático
    POST   /datasets/sample          gera 1 dataset sintético
    POST   /datasets/samples/all     gera/regera todas as bases sintéticas
    GET    /datasets/samples         lista catálogo de samples disponíveis
    GET    /datasets/{id}            metadata completo (com colunas/profile)
    GET    /datasets/{id}/preview    primeiras N linhas
    GET    /datasets/{id}/profile    perfil das colunas
    POST   /datasets/{id}/status     muda status (Draft/Validated/Certified)
    DELETE /datasets/{id}            apaga dataset (admin/owner)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetStatus
from app.models.user import User
from app.schemas.dataset import (
    DatasetCertifyRequest,
    DatasetColumnOut,
    DatasetOut,
    DatasetPreviewOut,
    DatasetSummaryOut,
    GenerateSampleRequest,
)
from app.services import dataset_service
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.permission_service import (
    accessible_workspaces,
    can_certify_dataset,
)
from app.services.lineage_service import get_dataset_lineage
from app.services.quality_engine import latest_quality, persist_quality_report
from app.schemas.phase9 import DatasetLineageOut, DatasetQualityOut
from app.utils.synthetic_data import SAMPLE_DATASETS
from database import get_db


router = APIRouter(prefix="/datasets", tags=["datasets"])


def _to_summary(ds: Dataset) -> DatasetSummaryOut:
    return DatasetSummaryOut(
        id=ds.id,
        name=ds.name,
        description=ds.description,
        workspace=ds.workspace,
        business_area=ds.business_area,
        source_type=ds.source_type,
        row_count=ds.row_count,
        column_count=ds.column_count,
        status=ds.status,
        created_by=ds.created_by,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


def _to_out(ds: Dataset) -> DatasetOut:
    return DatasetOut(
        id=ds.id,
        name=ds.name,
        description=ds.description,
        workspace=ds.workspace,
        business_area=ds.business_area,
        source_type=ds.source_type,
        source_data_source_id=ds.source_data_source_id,
        original_filename=ds.original_filename,
        file_size_bytes=ds.file_size_bytes,
        row_count=ds.row_count,
        column_count=ds.column_count,
        status=ds.status,
        created_by=ds.created_by,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
        certified_by=ds.certified_by,
        certified_at=ds.certified_at,
        columns=[
            DatasetColumnOut(**c.to_dict()) for c in ds.columns
        ],
    )


def _accessible(db: Session, user: User) -> list[Dataset]:
    all_ws = [d.workspace for d in db.query(Dataset.workspace).distinct().all()]
    allowed = set(accessible_workspaces(user, list(set(all_ws)) or []))
    q = db.query(Dataset)
    # Sempre permita ver datasets do workspace LATAM se o usuário tem LATAM no escopo,
    # mais qualquer outro do seu home workspace.
    if allowed:
        q = q.filter(Dataset.workspace.in_(list(allowed)))
    else:
        # role sem nenhum workspace acessível
        return []
    return q.order_by(Dataset.updated_at.desc()).all()


@router.get("", response_model=list[DatasetSummaryOut])
def list_datasets(
    workspace: str | None = None,
    business_area: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> list[DatasetSummaryOut]:
    items = _accessible(db, user)
    if workspace:
        items = [d for d in items if d.workspace == workspace]
    if business_area:
        items = [d for d in items if d.business_area == business_area]
    if status_filter:
        items = [d for d in items if d.status == status_filter]
    return [_to_summary(d) for d in items]


@router.get("/samples")
def list_samples(_: User = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "name": spec["name"],
            "description": spec["description"],
            "business_area": spec["business_area"],
            "workspace": spec["workspace"],
        }
        for spec in SAMPLE_DATASETS.values()
    ]


@router.post("/sample", response_model=DatasetOut)
def generate_sample(
    payload: GenerateSampleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("upload_dataset")),
) -> DatasetOut:
    if payload.name not in SAMPLE_DATASETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sample desconhecido: {payload.name}",
        )
    ds = dataset_service.create_dataset_from_sample(
        db,
        sample_name=payload.name,
        workspace=payload.workspace,
        created_by=user.email,
    )
    log_action(
        db,
        user_email=user.email,
        action="generate_sample_dataset",
        object_type="dataset",
        object_name=ds.name,
        workspace=ds.workspace,
        business_area=ds.business_area,
        details=f"dataset_id={ds.id} rows={ds.row_count}",
    )
    return _to_out(ds)


@router.post("/samples/all")
def generate_all_samples(
    force: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("upload_dataset")),
) -> list[DatasetSummaryOut]:
    created = dataset_service.generate_all_samples(
        db, workspace="LATAM", created_by=user.email, force=force,
    )
    log_action(
        db,
        user_email=user.email,
        action="generate_all_samples",
        object_type="dataset",
        object_name="bulk_samples",
        details=f"force={force} count={len(created)}",
    )
    return [_to_summary(d) for d in created]


@router.post("/upload", response_model=DatasetOut)
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_name: str = Form(...),
    description: str = Form(""),
    workspace: str = Form("LATAM"),
    business_area: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("upload_dataset")),
) -> DatasetOut:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo sem nome.",
        )

    # workspace OK?
    if workspace not in accessible_workspaces(user, [workspace]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem acesso ao workspace {workspace}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio.",
        )
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo maior que 50MB (limite da demo).",
        )

    try:
        ds = dataset_service.create_dataset_from_upload(
            db,
            file_bytes=content,
            original_filename=file.filename,
            dataset_name=dataset_name.strip() or Path(file.filename).stem,
            description=description,
            workspace=workspace,
            business_area=business_area,
            created_by=user.email,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    log_action(
        db,
        user_email=user.email,
        action="upload_dataset",
        object_type="dataset",
        object_name=ds.name,
        workspace=ds.workspace,
        business_area=ds.business_area,
        details=(
            f"dataset_id={ds.id} rows={ds.row_count} cols={ds.column_count} "
            f"file={file.filename} size={ds.file_size_bytes}"
        ),
    )
    return _to_out(ds)


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> DatasetOut:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    return _to_out(ds)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewOut)
def preview_dataset(
    dataset_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> DatasetPreviewOut:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit deve estar entre 1 e 1000.")
    try:
        data = dataset_service.get_preview(ds, limit=limit)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Arquivo processado não encontrado em disco.")
    return DatasetPreviewOut(**data)


@router.get("/{dataset_id}/profile", response_model=list[DatasetColumnOut])
def get_profile(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> list[DatasetColumnOut]:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    return [DatasetColumnOut(**c.to_dict()) for c in ds.columns]


@router.get("/{dataset_id}/lineage", response_model=DatasetLineageOut)
def dataset_lineage(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_lineage")),
) -> DatasetLineageOut:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    return get_dataset_lineage(db, ds)


@router.get("/{dataset_id}/quality", response_model=DatasetQualityOut)
def dataset_quality(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_datasets")),
) -> DatasetQualityOut:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    report = latest_quality(db, ds)
    if not report:
        raise HTTPException(status_code=404, detail="Nenhum quality report. Execute POST /quality/run.")
    return report


@router.post("/{dataset_id}/quality/run", response_model=DatasetQualityOut)
def run_dataset_quality(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("run_quality_checks")),
) -> DatasetQualityOut:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    try:
        report = persist_quality_report(db, ds)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Parquet não encontrado.")
    log_action(
        db,
        user_email=user.email,
        action="run_quality_checks",
        object_type="dataset",
        object_name=ds.name,
        workspace=ds.workspace,
        details=f"score={report.score}",
    )
    return report


@router.post("/{dataset_id}/status", response_model=DatasetOut)
def change_status(
    dataset_id: int,
    payload: DatasetCertifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")

    new_status = payload.status
    # Validated / Draft / Deprecated: o owner do dataset ou quem pode certify
    # pode mover. Certified exige certify_dataset.
    if new_status == DatasetStatus.CERTIFIED.value:
        if not can_certify_dataset(user, ds.business_area):
            raise HTTPException(
                status_code=403,
                detail="Sem permissão para certificar dataset.",
            )
    else:
        # Para outros status: precisa ser owner OU ter certify_dataset
        if ds.created_by != user.email and not can_certify_dataset(user, ds.business_area):
            raise HTTPException(
                status_code=403,
                detail="Apenas o owner ou um data steward pode mudar o status.",
            )

    try:
        ds = dataset_service.update_status(
            db, ds, new_status=new_status, actor_email=user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log_action(
        db,
        user_email=user.email,
        action="change_dataset_status",
        object_type="dataset",
        object_name=ds.name,
        workspace=ds.workspace,
        business_area=ds.business_area,
        details=f"new_status={new_status}",
    )
    return _to_out(ds)


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.created_by != user.email and not can_certify_dataset(user, ds.business_area):
        raise HTTPException(status_code=403, detail="Sem permissão para apagar.")

    name = ds.name
    workspace = ds.workspace
    business_area = ds.business_area

    # Limpa arquivos físicos (best effort)
    for path in (ds.raw_path, ds.processed_path):
        if path:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    db.delete(ds)
    db.commit()

    log_action(
        db,
        user_email=user.email,
        action="delete_dataset",
        object_type="dataset",
        object_name=name,
        workspace=workspace,
        business_area=business_area,
    )
    return {"ok": True}
