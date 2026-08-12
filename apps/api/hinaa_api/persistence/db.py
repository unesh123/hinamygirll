from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ..config import Settings
from .orm import Base


def make_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        database_path = make_url(database_url).database
        if database_path and database_path != ":memory:":
            Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        # StaticPool keeps a shared in-memory database across connections/tests.
        engine = create_engine(
            database_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def _sqlite_fk(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(database_url, future=True)


def init_db(settings: Settings) -> sessionmaker[Session]:
    global _session_factory
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
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
