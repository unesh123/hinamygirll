from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool

from ..config import Settings
from .orm import Base


def normalize_database_url(database_url: str) -> str:
    """Map provider-style Postgres URLs onto the psycopg (v3) SQLAlchemy driver."""
    url = database_url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def is_postgres_url(database_url: str | None) -> bool:
    return bool(database_url) and normalize_database_url(database_url).startswith("postgresql")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def make_engine(database_url: str) -> Engine:
    database_url = normalize_database_url(database_url)
    if database_url.startswith("sqlite"):
        database_path = make_url(database_url).database
        if database_path and database_path != ":memory:":
            Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        # Only in-memory SQLite needs a shared connection. File databases need
        # one connection per checkout: sharing a StaticPool connection across
        # concurrent auth/speech requests corrupts transaction boundaries.
        engine = create_engine(
            database_url,
            future=True,
            connect_args={"check_same_thread": False, "timeout": 15},
            poolclass=StaticPool if database_path in (None, "", ":memory:") else QueuePool,
        )

        @event.listens_for(engine, "connect")
        def _sqlite_fk(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            if database_path and database_path != ":memory:":
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=15000")
            cursor.close()

        return engine
    if database_url.startswith("postgresql"):
        return create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
            pool_size=_env_int("HINAA_DB_POOL_SIZE", 5),
            max_overflow=_env_int("HINAA_DB_MAX_OVERFLOW", 10),
            pool_recycle=_env_int("HINAA_DB_POOL_RECYCLE", 1800),
            pool_timeout=_env_int("HINAA_DB_POOL_TIMEOUT", 30),
        )
    return create_engine(database_url, future=True)


def init_db(settings: Settings) -> sessionmaker[Session]:
    global _session_factory
    engine = make_engine(settings.database_url)
    
    from .migrations import run_migrations
    run_migrations(engine)
            
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return _session_factory


_session_factory: sessionmaker[Session] | None = None


def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = init_db(settings)
    return _session_factory


def reset_session_factory() -> None:
    global _session_factory
    _session_factory = None


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
