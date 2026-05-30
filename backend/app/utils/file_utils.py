"""Helpers para arquivos de dataset.

- Detectar formato por extensão (CSV/XLSX/Parquet).
- Ler com Pandas com fallback de encoding.
- Salvar uploads de forma segura (nome sanitizado + UUID).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pandas as pd


_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_filename(name: str) -> str:
    name = name.strip().replace(" ", "_")
    name = _SAFE.sub("", name)
    return name[:120] or "file"


def unique_filename(original: str) -> str:
    return f"{uuid.uuid4().hex[:8]}_{sanitize_filename(original)}"


def detect_format(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in {"csv", "tsv", "txt"}:
        return "csv"
    if ext in {"xlsx", "xlsm", "xls"}:
        return "excel"
    if ext == "parquet":
        return "parquet"
    return "unknown"


def read_dataframe(path: str | Path) -> pd.DataFrame:
    """Lê CSV/XLSX/Parquet com tentativas de encoding (para CSV)."""
    p = Path(path)
    fmt = detect_format(p.name)
    if fmt == "csv":
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                return pd.read_csv(p, encoding=encoding)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(p, encoding="utf-8", errors="replace")
    if fmt == "excel":
        return pd.read_excel(p)
    if fmt == "parquet":
        return pd.read_parquet(p)
    raise ValueError(f"Formato não suportado: {p.suffix}")


def save_parquet(df: pd.DataFrame, path: str | Path) -> None:
    """Salva DataFrame em parquet (compacto + rápido de ler)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
