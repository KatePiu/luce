"""Crea il primo utente amministratore. Uso:

    python -m scripts.create_admin nicola.ratti@katepiu.com "password-sicura"
"""

import sys

sys.path.insert(0, ".")

from app.db import SessionLocal
from app.models import User
from app.security import hash_password


def main():
    if len(sys.argv) != 3:
        print("Uso: python -m scripts.create_admin <email> <password>")
        sys.exit(1)

    email, password = sys.argv[1], sys.argv[2]
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).one_or_none():
            print(f"Utente {email} già esistente.")
            return
        user = User(email=email, password_hash=hash_password(password), role="admin", display_name="Amministratore")
        db.add(user)
        db.commit()
        print(f"Utente admin creato: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
