"""Serviço de Dataset.

Centraliza:
    - persistência de uploads (CSV/XLSX)
    - geração de bases sintéticas
    - profiling
    - leitura de preview
    - mudanças de status (Draft/Validated/Certified/Deprecated)

Os arquivos físicos vão para:
    storage/uploads/      - original do usuário
    storage/processed/    - parquet normalizado para leituras rápidas
    storage/sample_data/  - parquet das bases sintéticas

Não permitimos execução arbitrária de código. Datasets são apenas dados
tabulares lidos com pandas.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetColumn, DatasetSourceType, DatasetStatus
from app.utils.file_utils import (
    detect_format,
    read_dataframe,
    save_parquet,
    unique_filename,
)
from app.utils.synthetic_data import SAMPLE_DATASETS
from app.services.profiling_service import (
    profile_dataframe,
    serialize_sample_values,
)
from config import settings


ALLOWED_UPLOAD_FORMATS = {"csv", "excel"}


# ---------------------------------------------------------------------------
# Persistência                                                              
# ---------------------------------------------------------------------------

def _persist_dataframe(
    db: Session,
    *,
    df: pd.DataFrame,
    name: str,
    description: str,
    workspace: str,
    business_area: str,
    source_type: str,
    created_by: str,
    original_filename: str = "",
    raw_path: str = "",
    file_size_bytes: int = 0,
    source_data_source_id: int | None = None,
    status: str = DatasetStatus.DRAFT.value,
) -> Dataset:
    """Persiste um DataFrame como Dataset + DatasetColumn + parquet processado."""
    ds = Dataset(
        name=name,
        description=description,
        workspace=workspace,
        business_area=business_area,
        source_type=source_type,
        source_data_source_id=source_data_source_id,
        original_filename=original_filename,
        raw_path=raw_path,
        file_size_bytes=file_size_bytes,
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
        status=status,
        created_by=created_by,
    )
    db.add(ds)
    db.flush()  # garante ID

    # Salva parquet processado
    processed_path = (settings.processed_dir / f"dataset_{ds.id}.parquet").resolve()
    save_parquet(df, processed_path)
    ds.processed_path = str(processed_path)

    # Profiling
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
                    if prof.mean_value is not None and not (isinstance(prof.mean_value, float) and math.isnan(prof.mean_value))
                    else None
                ),
                std_value=(
                    prof.std_value
                    if prof.std_value is not None and not (isinstance(prof.std_value, float) and math.isnan(prof.std_value))
                    else None
                ),
                sample_values=serialize_sample_values(prof.sample_values),
            )
        )

    db.commit()
    db.refresh(ds)
    return ds


# ---------------------------------------------------------------------------
# Upload de CSV/XLSX                                                        
# ---------------------------------------------------------------------------

def create_dataset_from_upload(
    db: Session,
    *,
    file_bytes: bytes,
    original_filename: str,
    dataset_name: str,
    description: str,
    workspace: str,
    business_area: str,
    created_by: str,
) -> Dataset:
    fmt = detect_format(original_filename)
    if fmt not in ALLOWED_UPLOAD_FORMATS:
        raise ValueError(f"Formato de arquivo não suportado: {original_filename}")

    raw_name = unique_filename(original_filename)
    raw_path = (settings.upload_dir / raw_name).resolve()
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(file_bytes)

    try:
        df = read_dataframe(raw_path)
    except Exception as exc:
        raw_path.unlink(missing_ok=True)
        raise ValueError(f"Falha ao ler arquivo: {exc}") from exc

    if df.empty:
        raise ValueError("Arquivo não contém linhas de dados.")

    return _persist_dataframe(
        db,
        df=df,
        name=dataset_name,
        description=description,
        workspace=workspace,
        business_area=business_area,
        source_type=DatasetSourceType.UPLOAD.value,
        created_by=created_by,
        original_filename=original_filename,
        raw_path=str(raw_path),
        file_size_bytes=len(file_bytes),
    )


# ---------------------------------------------------------------------------
# Geração de bases sintéticas                                               
# ---------------------------------------------------------------------------

def create_dataset_from_sample(
    db: Session,
    *,
    sample_name: str,
    workspace: str,
    created_by: str,
) -> Dataset:
    if sample_name not in SAMPLE_DATASETS:
        raise KeyError(f"Sample desconhecido: {sample_name}")
    spec = SAMPLE_DATASETS[sample_name]
    df: pd.DataFrame = spec["generator"]()

    # Persistir também o "raw" parquet em sample_data para cachear (opcional).
    sample_path = (settings.sample_data_dir / f"{sample_name}.parquet").resolve()
    save_parquet(df, sample_path)

    return _persist_dataframe(
        db,
        df=df,
        name=spec["name"],
        description=spec["description"],
        workspace=workspace or spec["workspace"],
        business_area=spec["business_area"],
        source_type=DatasetSourceType.SAMPLE.value,
        created_by=created_by,
        original_filename=f"{sample_name}.parquet",
        raw_path=str(sample_path),
        file_size_bytes=sample_path.stat().st_size,
    )


def generate_all_samples(
    db: Session,
    *,
    workspace: str = "LATAM",
    created_by: str = "system",
    force: bool = False,
) -> list[Dataset]:
    """Gera (ou regenera) todas as bases sintéticas. Útil para seed e botão "Gerar tudo"."""
    out: list[Dataset] = []
    for name in SAMPLE_DATASETS.keys():
        existing = (
            db.query(Dataset)
            .filter(Dataset.name == name, Dataset.source_type == DatasetSourceType.SAMPLE.value)
            .first()
        )
        if existing and not force:
            out.append(existing)
            continue
        if existing and force:
            # Apaga colunas e cria do zero.
            db.delete(existing)
            db.commit()
        out.append(create_dataset_from_sample(
            db, sample_name=name, workspace=workspace, created_by=created_by,
        ))
    return out


# ---------------------------------------------------------------------------
# Leitura / Preview                                                         
# ---------------------------------------------------------------------------

def _load_processed_df(ds: Dataset) -> pd.DataFrame:
    p = Path(ds.processed_path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet processado não encontrado: {p}")
    return pd.read_parquet(p)


def get_preview(ds: Dataset, *, limit: int = 100) -> dict[str, Any]:
    """Retorna primeiras `limit` linhas + nomes de colunas."""
    df = _load_processed_df(ds)
    columns = [str(c) for c in df.columns]
    head = df.head(limit).copy()
    # Datetime -> ISO string para serialização JSON segura
    for c in head.columns:
        if pd.api.types.is_datetime64_any_dtype(head[c]):
            head[c] = head[c].dt.strftime("%Y-%m-%d")
    head = head.where(pd.notna(head), None)
    rows = head.to_dict(orient="records")
    return {
        "dataset_id": ds.id,
        "name": ds.name,
        "row_count": ds.row_count,
        "column_count": ds.column_count,
        "columns": columns,
        "rows": rows,
        "truncated": bool(ds.row_count > limit),
    }


# ---------------------------------------------------------------------------
# Mudança de status                                                         
# ---------------------------------------------------------------------------

VALID_STATUS = {s.value for s in DatasetStatus}


def update_status(
    db: Session,
    ds: Dataset,
    *,
    new_status: str,
    actor_email: str,
) -> Dataset:
    if new_status not in VALID_STATUS:
        raise ValueError(f"Status inválido: {new_status}")
    ds.status = new_status
    if new_status == DatasetStatus.CERTIFIED.value:
        ds.certified_by = actor_email
        ds.certified_at = datetime.utcnow()
    db.commit()
    db.refresh(ds)
    return ds
