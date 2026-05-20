import logging
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()

engine: Engine | None = None
SessionLocal: sessionmaker | None = None
DATABASE_URL: str = ""
DB_BACKEND: str = "uninitialized"


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


def resolve_preferred_database_url() -> str:
    if os.getenv("DATABASE_FORCE_SQLITE", "").lower() in {"1", "true", "yes"}:
        return _sqlite_url()

    url = os.getenv("DATABASE_URL") or _build_url_from_pg_env()
    if not url:
        return _sqlite_url()
    url = _normalize_postgres_url(url)
    if url.startswith("postgresql://") and "sslmode=" not in url:
        if os.getenv("DATABASE_SSL", "").lower() in {"1", "true", "require"}:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
    return url


def _sqlite_url() -> str:
    path = os.getenv("SQLITE_PATH", "/tmp/mcp-bank.db")
    if path == ":memory:":
        return "sqlite:///:memory:"
    if path.startswith("sqlite:"):
        return path
    return f"sqlite:///{path}"


def _engine_connect_args(url: str) -> dict[str, object]:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    if url.startswith("postgresql"):
        return {"connect_timeout": int(os.getenv("DATABASE_CONNECT_TIMEOUT", "5"))}
    return {}


def configure_engine(url: str, backend: str) -> None:
    global engine, SessionLocal, DATABASE_URL, DB_BACKEND

    connect_args = _engine_connect_args(url)
    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=not url.startswith("sqlite"),
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    DATABASE_URL = url
    DB_BACKEND = backend
    logger.info("Database configured: backend=%s url=%s", backend, _safe_url(url))


def _safe_url(url: str) -> str:
    if "@" not in url:
        return url
    return url.split("@", 1)[-1]


def probe_connection() -> None:
    if engine is None:
        raise RuntimeError("Database engine not configured")
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def initialize_database() -> str:
    """Pick PostgreSQL when reachable, otherwise SQLite so the demo stays up."""
    preferred = resolve_preferred_database_url()

    if preferred.startswith("sqlite"):
        configure_engine(preferred, "sqlite")
        probe_connection()
        return DB_BACKEND

    try:
        configure_engine(preferred, "postgresql")
        probe_connection()
        return DB_BACKEND
    except Exception as exc:
        fallback = _sqlite_url()
        logger.warning(
            "PostgreSQL unavailable (%s). Falling back to SQLite at %s",
            exc,
            fallback,
        )
        configure_engine(fallback, "sqlite-fallback")
        probe_connection()
        return DB_BACKEND


def get_db_status() -> dict[str, str]:
    return {
        "backend": DB_BACKEND,
        "url_hint": _safe_url(DATABASE_URL),
    }


def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


initialize_database()
