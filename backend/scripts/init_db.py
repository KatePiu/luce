"""Crea le tabelle del database eseguendo backend/db/schema.sql.

Con docker-compose in locale questo avviene automaticamente al primo avvio.
Su un hosting come Render, dove il database è un servizio gestito separato,
va eseguito una volta a mano dopo il primo deploy:

    python -m scripts.init_db
"""

import sys

sys.path.insert(0, ".")

from app.db import engine
from app.schema_tools import apply_schema


def main():
    count = apply_schema(engine)
    print(f"Schema applicato correttamente ({count} istruzioni).")


if __name__ == "__main__":
    main()
