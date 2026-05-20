import logging
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _build_url_from_pg_env() -> str | None:
    host = os.getenv("PGHOST")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    database = os.getenv("PGDATABASE")
    port = os.getenv("PGPORT", "5432")
    if not all([host, user, password, database]):
        return None
    safe_user = quote_plus(user)
    safe_password = quote_plus(password)
    return (
        f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{database}"
    )


def resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL") or _build_url_from_pg_env()
    if not url:
        return "sqlite:///bank.db"
    url = _normalize_postgres_url(url)
    if url.startswith("postgresql://") and "sslmode=" not in url:
        if os.getenv("DATABASE_SSL", "").lower() in {"1", "true", "require"}:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
    return url


DATABASE_URL = resolve_database_url()

connect_args: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif DATABASE_URL.startswith("postgresql"):
    connect_args = {"connect_timeout": 10}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)
logger.info(
    "Database engine ready (%s)",
    "postgresql" if DATABASE_URL.startswith("postgresql") else "sqlite",
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to get a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
