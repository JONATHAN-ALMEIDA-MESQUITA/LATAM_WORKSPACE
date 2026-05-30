"""Data Lineage service (Phase 9)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.forecast import Forecast
from app.models.lineage import LineageEdge
from app.models.pipeline import Pipeline, PipelineStep, StepType
from app.schemas.phase9 import DatasetLineageOut, LineageEdgeOut, LineageNode


def record_edge(
    db: Session,
    *,
    to_dataset_id: int,
    from_dataset_id: int | None,
    relation_type: str,
    entity_type: str,
    entity_id: int | None,
    entity_name: str,
) -> LineageEdge:
    existing = (
        db.query(LineageEdge)
        .filter(
            LineageEdge.to_dataset_id == to_dataset_id,
            LineageEdge.from_dataset_id == from_dataset_id,
            LineageEdge.relation_type == relation_type,
            LineageEdge.entity_id == entity_id,
        )
        .first()
    )
    if existing:
        return existing
    edge = LineageEdge(
        from_dataset_id=from_dataset_id,
        to_dataset_id=to_dataset_id,
        relation_type=relation_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    db.add(edge)
    db.flush()
    return edge


def _node(ds: Dataset) -> LineageNode:
    return LineageNode(
        id=ds.id,
        name=ds.name,
        source_type=ds.source_type,
        workspace=ds.workspace,
    )


def rebuild_lineage_from_entities(db: Session) -> int:
    """Reconstrói edges a partir de pipelines e forecasts (idempotente)."""
    created = 0
    for p in db.query(Pipeline).all():
        steps = (
            db.query(PipelineStep)
            .filter(PipelineStep.pipeline_id == p.id)
            .order_by(PipelineStep.order_index)
            .all()
        )
        source_ids: set[int] = set()
        for s in steps:
            cfg = s.config_dict()
            if s.step_type == StepType.SOURCE.value and cfg.get("dataset_id"):
                source_ids.add(int(cfg["dataset_id"]))
            if s.step_type == StepType.JOIN.value and cfg.get("right_dataset_id"):
                source_ids.add(int(cfg["right_dataset_id"]))
        target_ds_id = None
        for run in p.runs:
            if run.target_dataset_id:
                target_ds_id = run.target_dataset_id
                break
        if target_ds_id:
            for sid in source_ids:
                record_edge(
                    db,
                    from_dataset_id=sid,
                    to_dataset_id=target_ds_id,
                    relation_type="pipeline",
                    entity_type="pipeline",
                    entity_id=p.id,
                    entity_name=p.name,
                )
                created += 1
    for f in db.query(Forecast).filter(Forecast.output_dataset_id.isnot(None)).all():
        if f.source_dataset_id and f.output_dataset_id:
            record_edge(
                db,
                from_dataset_id=f.source_dataset_id,
                to_dataset_id=f.output_dataset_id,
                relation_type="forecast",
                entity_type="forecast",
                entity_id=f.id,
                entity_name=f.name,
            )
            created += 1
    db.commit()
    return created


def get_dataset_lineage(db: Session, ds: Dataset) -> DatasetLineageOut:
    edges = (
        db.query(LineageEdge)
        .filter(
            (LineageEdge.to_dataset_id == ds.id) | (LineageEdge.from_dataset_id == ds.id)
        )
        .all()
    )
    if not edges:
        rebuild_lineage_from_entities(db)
        edges = (
            db.query(LineageEdge)
            .filter(
                (LineageEdge.to_dataset_id == ds.id) | (LineageEdge.from_dataset_id == ds.id)
            )
            .all()
        )

    upstream_ids: set[int] = set()
    downstream_ids: set[int] = set()
    edge_out: list[LineageEdgeOut] = []

    for e in edges:
        edge_out.append(
            LineageEdgeOut(
                from_dataset_id=e.from_dataset_id,
                to_dataset_id=e.to_dataset_id,
                relation_type=e.relation_type,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                entity_name=e.entity_name,
            )
        )
        if e.to_dataset_id == ds.id and e.from_dataset_id:
            upstream_ids.add(e.from_dataset_id)
        if e.from_dataset_id == ds.id:
            downstream_ids.add(e.to_dataset_id)

    upstream = [
        _node(d)
        for d in db.query(Dataset).filter(Dataset.id.in_(upstream_ids)).all()
    ] if upstream_ids else []
    downstream = [
        _node(d)
        for d in db.query(Dataset).filter(Dataset.id.in_(downstream_ids)).all()
    ] if downstream_ids else []

    return DatasetLineageOut(
        dataset_id=ds.id,
        dataset_name=ds.name,
        upstream=upstream,
        downstream=downstream,
        edges=edge_out,
    )
