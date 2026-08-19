"""Crea le tabelle del database eseguendo backend/db/schema.sql.

Con docker-compose in locale questo avviene automaticamente al primo avvio.
Su un hosting come Render, dove il database è un servizio gestito separato,
va eseguito una volta a mano dopo il primo deploy:

    python -m scripts.init_db
"""

import sys
from pathlib import Path

sys.path.insert(0, ".")

from sqlalchemy import text

from app.db import engine

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def _strip_sql_comments(sql: str) -> str:
    """Rimuove i commenti '-- ...' riga per riga, PRIMA di dividere sugli ';':
    dividere prima e filtrare dopo è sbagliato, perché un commento messo subito
    dopo il ';' della istruzione precedente farebbe scartare per errore anche
    l'istruzione reale che segue nella stessa porzione di testo."""
    lines = []
    for line in sql.splitlines():
        idx = line.find("--")
        lines.append(line[:idx] if idx != -1 else line)
    return "\n".join(lines)


def main():
    sql = _strip_sql_comments(SCHEMA_PATH.read_text())
    # Eseguito istruzione per istruzione (non un unico blocco): più affidabile
    # tra i diversi driver/versioni di Postgres per uno script con più CREATE.
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    print(f"Schema applicato correttamente ({len(statements)} istruzioni).")


if __name__ == "__main__":
    main()
