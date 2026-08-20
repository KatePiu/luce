"""Applica backend/db/schema.sql al database configurato. Usato sia dallo
script CLI (scripts/init_db.py) sia dall'endpoint admin di emergenza, per
evitare di duplicare la logica di split/esecuzione delle istruzioni."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def _strip_sql_comments(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        idx = line.find("--")
        lines.append(line[:idx] if idx != -1 else line)
    return "\n".join(lines)


def apply_schema(engine: Engine) -> int:
    sql = _strip_sql_comments(SCHEMA_PATH.read_text())
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    return len(statements)
