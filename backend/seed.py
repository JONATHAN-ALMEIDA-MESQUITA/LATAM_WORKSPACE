"""Script de seed - popula o SQLite com:

- Workspaces (LATAM, Brazil, Colombia, Mexico, Argentina, Chile, Peru)
- Usuários mockados (8 perfis distintos)

Uso:
    python seed.py
"""

from __future__ import annotations

from app.models.user import Role, User
from app.models.workspace import Workspace, WorkspaceName
from database import SessionLocal, init_db


WORKSPACES_SEED: list[dict] = [
    {
        "name": WorkspaceName.LATAM.value,
        "description": "Visão regional consolidada - restrito a gestão regional.",
        "scope": "regional",
    },
    {"name": WorkspaceName.BRAZIL.value, "description": "Operações Brasil.", "scope": "country"},
    {"name": WorkspaceName.COLOMBIA.value, "description": "Operações Colômbia.", "scope": "country"},
    {"name": WorkspaceName.MEXICO.value, "description": "Operações México.", "scope": "country"},
    {"name": WorkspaceName.ARGENTINA.value, "description": "Operações Argentina.", "scope": "country"},
    {"name": WorkspaceName.CHILE.value, "description": "Operações Chile.", "scope": "country"},
    {"name": WorkspaceName.PERU.value, "description": "Operações Peru.", "scope": "country"},
]


USERS_SEED: list[dict] = [
    {
        "email": "admin@latam.com",
        "full_name": "Ana Admin",
        "role": Role.PLATFORM_ADMIN.value,
        "home_workspace": WorkspaceName.LATAM.value,
    },
    {
        "email": "data.dev@latam.com",
        "full_name": "Diego Data Dev",
        "role": Role.DATA_DEVELOPER.value,
        "home_workspace": WorkspaceName.LATAM.value,
    },
    {
        "email": "analyst.br@latam.com",
        "full_name": "Bruna Analyst BR",
        "role": Role.DATA_ANALYST.value,
        "home_workspace": WorkspaceName.BRAZIL.value,
    },
    {
        "email": "finance.owner@latam.com",
        "full_name": "Felipe Finance Owner",
        "role": Role.FINANCE_OWNER.value,
        "home_workspace": WorkspaceName.LATAM.value,
    },
    {
        "email": "operations.owner@latam.com",
        "full_name": "Olivia Ops Owner",
        "role": Role.OPERATIONS_OWNER.value,
        "home_workspace": WorkspaceName.LATAM.value,
    },
    {
        "email": "regional.manager@latam.com",
        "full_name": "Renata Regional",
        "role": Role.LATAM_EXECUTIVE_VIEWER.value,
        "home_workspace": WorkspaceName.LATAM.value,
    },
    {
        "email": "viewer.br@latam.com",
        "full_name": "Vitor Viewer BR",
        "role": Role.VIEWER.value,
        "home_workspace": WorkspaceName.BRAZIL.value,
    },
    {
        "email": "ml.owner@latam.com",
        "full_name": "Marina ML Owner",
        "role": Role.ML_OWNER.value,
        "home_workspace": WorkspaceName.LATAM.value,
    },
]


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        # Workspaces (upsert por nome).
        for ws in WORKSPACES_SEED:
            existing = db.query(Workspace).filter(Workspace.name == ws["name"]).first()
            if existing:
                existing.description = ws["description"]
                existing.scope = ws["scope"]
            else:
                db.add(Workspace(**ws))
        db.commit()

        # Usuários (upsert por email).
        for u in USERS_SEED:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                existing.full_name = u["full_name"]
                existing.role = u["role"]
                existing.home_workspace = u["home_workspace"]
                existing.is_active = True
            else:
                db.add(User(**u))
        db.commit()

        print(">>> Seed concluído com sucesso.")
        print(f"    Workspaces: {db.query(Workspace).count()}")
        print(f"    Users:      {db.query(User).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
