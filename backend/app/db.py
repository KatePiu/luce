from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


def _normalize_database_url(url: str) -> str:
    """Molti hosting (Render, Railway, Heroku-style) forniscono un DATABASE_URL
    con schema 'postgres://' o 'postgresql://', senza indicare il driver. Il
    progetto usa psycopg3: qui si riscrive lo schema in 'postgresql+psycopg://'
    così l'URL fornito dall'hosting funziona senza doverlo modificare a mano."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


engine = create_engine(_normalize_database_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
