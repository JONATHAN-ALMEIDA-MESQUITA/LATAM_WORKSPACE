"""Seed das tabelas dimensionais para Ad-Hoc Report (joins).

Cria client_master e product_catalog se ainda nao existirem.
Idempotente — seguro rodar apos seed.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.dataset import Dataset, DatasetSourceType
from app.services.dataset_service import create_dataset_from_sample
from database import SessionLocal, init_db

DEMO_TABLES = ["client_master", "product_catalog"]
DEFAULT_OWNER = "admin@latam.com"


def main() -> None:
    init_db()
    session = SessionLocal()
    try:
        created = []
        for name in DEMO_TABLES:
            existing = (
                session.query(Dataset)
                .filter(Dataset.name == name, Dataset.source_type == DatasetSourceType.SAMPLE.value)
                .first()
            )
            if existing:
                print(f"  skip {name} (id={existing.id}, rows={existing.row_count})")
                continue
            ds = create_dataset_from_sample(
                session,
                sample_name=name,
                workspace="LATAM",
                created_by=DEFAULT_OWNER,
            )
            session.commit()
            created.append(ds.name)
            print(f"  created {ds.name} (id={ds.id}, rows={ds.row_count})")
        if not created:
            print("Seed report tables OK — dimensões já existem.")
        else:
            print(f"Seed report tables OK — criadas: {', '.join(created)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
