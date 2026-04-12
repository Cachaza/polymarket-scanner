from __future__ import annotations

from pathlib import Path


def get_schema_path() -> Path:
    candidates = (
        Path(__file__).resolve().parent.parent / "sql" / "schema.sql",
        Path.cwd() / "sql" / "schema.sql",
        Path("/app/sql/schema.sql"),
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("Could not locate sql/schema.sql")
