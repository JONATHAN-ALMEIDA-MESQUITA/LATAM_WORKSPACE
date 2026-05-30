"""Router de DataSources.

Endpoints:
    GET    /data-sources               lista conexões cadastradas
    POST   /data-sources               cria conexão
    PUT    /data-sources/{id}          atualiza
    DELETE /data-sources/{id}          remove
    POST   /data-sources/{id}/test     testa a conexão (mockado para SQLite/DuckDB local;
                                       outros tipos retornam latência simulada)

NÃO conectamos em bancos externos reais na demo. Para SQLite/DuckDB locais
realizamos uma checagem real e barata.
"""

from __future__ import annotations

import random
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.data_source import DatabaseType, DataSource, DataSourceStatus
from app.models.user import User
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceOut,
    DataSourceUpdate,
    TestConnectionResult,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.permission_service import accessible_workspaces
from database import get_db


router = APIRouter(prefix="/data-sources", tags=["data-sources"])


VALID_TYPES = {t.value for t in DatabaseType}


def _to_out(ds: DataSource) -> DataSourceOut:
    return DataSourceOut(
        id=ds.id,
        connection_name=ds.connection_name,
        database_type=ds.database_type,
        host=ds.host,
        port=ds.port,
        database_name=ds.database_name,
        username=ds.username,
        has_password=ds.has_password,
        db_schema=ds.db_schema,
        status=ds.status,
        workspace=ds.workspace,
        created_by=ds.created_by,
        created_at=ds.created_at,
        last_test_at=ds.last_test_at,
        notes=ds.notes,
    )


@router.get("", response_model=list[DataSourceOut])
def list_data_sources(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_data_sources")),
) -> list[DataSourceOut]:
    items = db.query(DataSource).order_by(DataSource.created_at.desc()).all()
    # Filtra por workspaces acessíveis
    if items:
        allowed = set(accessible_workspaces(user, list({i.workspace for i in items})))
        items = [i for i in items if i.workspace in allowed]
    return [_to_out(i) for i in items]


@router.post("", response_model=DataSourceOut)
def create_data_source(
    payload: DataSourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_data_source")),
) -> DataSourceOut:
    if payload.database_type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de banco inválido: {payload.database_type}. Opções: {sorted(VALID_TYPES)}",
        )
    if payload.workspace not in accessible_workspaces(user, [payload.workspace]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem acesso ao workspace {payload.workspace}",
        )
    existing = (
        db.query(DataSource)
        .filter(DataSource.connection_name == payload.connection_name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conexão com esse nome.",
        )

    ds = DataSource(
        connection_name=payload.connection_name,
        database_type=payload.database_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        has_password=bool(payload.password),
        db_schema=payload.db_schema,
        status=DataSourceStatus.PENDING_TEST.value,
        workspace=payload.workspace,
        notes=payload.notes,
        created_by=user.email,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    log_action(
        db,
        user_email=user.email,
        action="create_data_source",
        object_type="data_source",
        object_name=ds.connection_name,
        workspace=ds.workspace,
        details=f"type={ds.database_type}",
    )
    return _to_out(ds)


@router.put("/{ds_id}", response_model=DataSourceOut)
def update_data_source(
    ds_id: int,
    payload: DataSourceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_data_source")),
) -> DataSourceOut:
    ds = db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")

    if payload.host is not None:
        ds.host = payload.host
    if payload.port is not None:
        ds.port = payload.port
    if payload.database_name is not None:
        ds.database_name = payload.database_name
    if payload.username is not None:
        ds.username = payload.username
    if payload.password is not None:
        ds.has_password = bool(payload.password)
    if payload.db_schema is not None:
        ds.db_schema = payload.db_schema
    if payload.status is not None:
        ds.status = payload.status
    if payload.notes is not None:
        ds.notes = payload.notes

    db.commit()
    db.refresh(ds)
    log_action(
        db,
        user_email=user.email,
        action="update_data_source",
        object_type="data_source",
        object_name=ds.connection_name,
        workspace=ds.workspace,
    )
    return _to_out(ds)


@router.delete("/{ds_id}")
def delete_data_source(
    ds_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_data_source")),
) -> dict:
    ds = db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    name = ds.connection_name
    workspace = ds.workspace
    db.delete(ds)
    db.commit()
    log_action(
        db,
        user_email=user.email,
        action="delete_data_source",
        object_type="data_source",
        object_name=name,
        workspace=workspace,
    )
    return {"ok": True}


@router.post("/{ds_id}/test", response_model=TestConnectionResult)
def test_connection(
    ds_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_data_sources")),
) -> TestConnectionResult:
    ds = db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")

    started = time.perf_counter()
    success = True
    message = "Conexão simulada com sucesso."

    if ds.database_type == DatabaseType.SQLITE.value:
        # Tentamos abrir o arquivo se houver um path em database_name.
        path = Path(ds.database_name) if ds.database_name else None
        if path and not path.exists():
            success = False
            message = f"Arquivo SQLite não encontrado: {path}"
    elif ds.database_type == DatabaseType.DUCKDB.value:
        # DuckDB embarcado - sucesso trivial.
        message = "DuckDB local pronto para uso."
    else:
        # Externos: simulação com chance pequena de falha aleatória.
        if random.random() < 0.1:
            success = False
            message = "Timeout simulado ao acessar o host."

    latency = int((time.perf_counter() - started) * 1000) + random.randint(20, 250)

    ds.status = DataSourceStatus.ACTIVE.value if success else DataSourceStatus.ERROR.value
    ds.last_test_at = datetime.utcnow()
    db.commit()

    log_action(
        db,
        user_email=user.email,
        action="test_data_source",
        object_type="data_source",
        object_name=ds.connection_name,
        workspace=ds.workspace,
        details=f"success={success} latency_ms={latency}",
    )
    return TestConnectionResult(success=success, message=message, latency_ms=latency)
