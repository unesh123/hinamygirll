"""Engine config, migrations (SQLite + Postgres), Alembic baseline, SQLite->Postgres copy."""

from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from hinaa_api.persistence import sqlcompat
from hinaa_api.persistence.copy_sqlite_to_postgres import copy_database, main as copy_main
from hinaa_api.persistence.db import is_postgres_url, make_engine, normalize_database_url
from hinaa_api.persistence.migrations import MIGRATIONS, get_migration_status, run_migrations
from hinaa_api.persistence.orm import Project, SalesRecord

PG_URL = os.environ.get("HINAA_TEST_DATABASE_URL", "").strip()
needs_pg = pytest.mark.skipif(not PG_URL, reason="HINAA_TEST_DATABASE_URL not set")
API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scratch_pg_url():
    """A throwaway Postgres database, dropped afterwards."""
    base = make_url(normalize_database_url(PG_URL))
    name = f"hinaa_t_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield base.set(database=name).render_as_string(hide_password=False)
    finally:
        sqlcompat.reset_pools()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _alembic_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


# ── engine configuration ──


def test_normalize_database_url_maps_provider_urls_to_psycopg():
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("sqlite+pysqlite:///x.db") == "sqlite+pysqlite:///x.db"
    assert is_postgres_url("postgres://u@h/db") and not is_postgres_url("sqlite:///x.db")


def test_postgres_engine_config_from_env(monkeypatch):
    monkeypatch.setenv("HINAA_DB_POOL_SIZE", "3")
    monkeypatch.setenv("HINAA_DB_MAX_OVERFLOW", "7")
    monkeypatch.setenv("HINAA_DB_POOL_RECYCLE", "60")
    engine = make_engine("postgres://u:p@localhost:1/db")  # lazy: never connects
    assert engine.dialect.name == "postgresql" and engine.dialect.driver == "psycopg"
    assert engine.pool.size() == 3
    assert engine.pool._max_overflow == 7
    assert engine.pool._recycle == 60
    assert engine.pool._pre_ping is True


def test_postgres_engine_defaults_ignore_bad_env(monkeypatch):
    monkeypatch.setenv("HINAA_DB_POOL_SIZE", "not-a-number")
    engine = make_engine("postgresql+psycopg://u@localhost:1/db")
    assert engine.pool.size() == 5


def test_sqlcompat_pg_target_rules(monkeypatch):
    monkeypatch.setenv("HINAA_DATABASE_URL", "postgres://u@h/db")
    assert sqlcompat.pg_target("x.db", is_default=True) == "postgresql+psycopg://u@h/db"
    assert sqlcompat.pg_target("x.db", is_default=False) is None
    assert sqlcompat.pg_target("postgresql://u@h/other", is_default=False) == "postgresql+psycopg://u@h/other"
    monkeypatch.setenv("HINAA_DATABASE_URL", "sqlite:///x.db")
    assert sqlcompat.pg_target("x.db", is_default=True) is None


def test_sqlcompat_translation():
    sql = sqlcompat._translate("CREATE TABLE IF NOT EXISTS t_x (id INTEGER PRIMARY KEY AUTOINCREMENT, v REAL, b BLOB)")
    assert "BIGSERIAL PRIMARY KEY" in sql and "DOUBLE PRECISION" in sql and "BYTEA" in sql
    assert sqlcompat._serial_columns["t_x"] == "id"
    assert sqlcompat._translate("PRAGMA journal_mode=WAL") is None
    assert sqlcompat._translate("SELECT * FROM t WHERE a = ? AND b LIKE '50%?'") == (
        "SELECT * FROM t WHERE a = %s AND b LIKE '50%%?'"
    )
    assert sqlcompat._translate("INSERT OR IGNORE INTO t (a) VALUES (?)").endswith("ON CONFLICT DO NOTHING")
    with pytest.raises(NotImplementedError):
        sqlcompat._translate("INSERT OR REPLACE INTO t (a) VALUES (?)")


# ── migrations ──


def test_migrations_run_and_are_idempotent_on_sqlite(tmp_path):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'm.db'}")
    first = run_migrations(engine)
    assert first == [version for version, _, _ in MIGRATIONS]
    assert run_migrations(engine) == []
    status = get_migration_status(engine)
    assert not status["pending"] and len(status["applied"]) == len(MIGRATIONS)
    assert "reminders" in inspect(engine).get_table_names()


@needs_pg
def test_migrations_run_and_are_idempotent_on_postgres(scratch_pg_url):
    engine = make_engine(scratch_pg_url)
    try:
        assert run_migrations(engine) == [version for version, _, _ in MIGRATIONS]
        assert run_migrations(engine) == []
        sqlite_engine = make_engine("sqlite+pysqlite:///:memory:")
        run_migrations(sqlite_engine)
        assert set(inspect(engine).get_table_names()) - {"schema_migrations"} == (
            set(inspect(sqlite_engine).get_table_names()) - {"schema_migrations"}
        )
    finally:
        engine.dispose()


@needs_pg
def test_concurrent_startup_migrations_are_serialised(scratch_pg_url):
    from concurrent.futures import ThreadPoolExecutor

    engines = [make_engine(scratch_pg_url) for _ in range(3)]
    try:
        with ThreadPoolExecutor(3) as pool:
            results = list(pool.map(run_migrations, engines))
        assert sorted(len(r) for r in results) == [0, 0, len(MIGRATIONS)]
    finally:
        for e in engines:
            e.dispose()


# ── alembic ──


def test_alembic_baseline_stamps_existing_sqlite_database(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'a.db'}"
    engine = make_engine(url)
    run_migrations(engine)
    with engine.connect() as conn:
        before = conn.execute(text("SELECT version, applied_at FROM schema_migrations ORDER BY version")).all()

    monkeypatch.setenv("HINAA_DATABASE_URL", url)
    command.upgrade(_alembic_config(), "head")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_baseline"
        after = conn.execute(text("SELECT version, applied_at FROM schema_migrations ORDER BY version")).all()
    assert after == before  # nothing re-applied

    command.upgrade(_alembic_config(), "head")  # idempotent


def test_alembic_upgrade_creates_fresh_sqlite_database(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'fresh.db'}"
    monkeypatch.setenv("HINAA_DATABASE_URL", url)
    command.upgrade(_alembic_config(), "head")
    tables = set(inspect(make_engine(url)).get_table_names())
    assert {"alembic_version", "schema_migrations", "reminders", "projects"} <= tables


@needs_pg
def test_alembic_baseline_on_postgres(scratch_pg_url, monkeypatch):
    monkeypatch.setenv("HINAA_DATABASE_URL", scratch_pg_url)
    engine = make_engine(scratch_pg_url)
    try:
        run_migrations(engine)
        command.upgrade(_alembic_config(), "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_baseline"
            assert conn.execute(text("SELECT count(*) FROM schema_migrations")).scalar_one() == len(MIGRATIONS)
    finally:
        engine.dispose()


# ── sqlite -> postgres copy ──


def _seed_sqlite(path: Path) -> str:
    url = f"sqlite+pysqlite:///{path}"
    engine = make_engine(url)
    run_migrations(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Project(id="p1", user_id="u1", name="Alpha"),
                Project(id="p2", user_id="u1", name="Beta"),
                SalesRecord(id="s1", user_id="u1", occurred_on=date(2026, 1, 2), amount=Decimal("12.50")),
            ]
        )
        session.commit()
    engine.dispose()
    return url


@needs_pg
def test_copy_sqlite_to_postgres_is_idempotent_and_verified(tmp_path, scratch_pg_url, capsys):
    source_url = _seed_sqlite(tmp_path / "src.db")

    results = copy_database(source_url, scratch_pg_url)
    counts = {r.table: (r.source, r.target) for r in results}
    assert counts["projects"] == (2, 2) and counts["sales_records"] == (1, 1)
    assert all(r.ok for r in results)

    # Second run: still exactly the same rows, exit code 0 via the CLI.
    assert copy_main(["--from", source_url, "--to", scratch_pg_url]) == 0
    out = capsys.readouterr().out
    assert "0 mismatches" in out
    engine = make_engine(scratch_pg_url)
    with engine.connect() as conn:
        assert conn.execute(select(Project.__table__.c.name).order_by(Project.__table__.c.name)).scalars().all() == [
            "Alpha",
            "Beta",
        ]
        assert conn.execute(select(SalesRecord.__table__.c.amount)).scalar_one() == Decimal("12.50")
    engine.dispose()


@needs_pg
def test_copy_runtime_store_file_into_runtime_schema(tmp_path, scratch_pg_url):
    from hinaa_api.security.store import SecurityStore

    source_url = _seed_sqlite(tmp_path / "src.db")
    runtime_file = tmp_path / "hinaa_autopilot.db"
    store = SecurityStore(runtime_file)
    store.append_audit_event(
        event_id="e1", timestamp=1.0, tenant_id="t", subject_id="s", action="a", resource="r",
        decision="allow", reason_code="ok", prev_hash="0", event_hash="h1", signature="sig",
    )

    for _ in range(2):  # idempotent
        results = copy_database(source_url, scratch_pg_url, [runtime_file])
    audit = next(r for r in results if r.table == f"{sqlcompat.RUNTIME_SCHEMA}.audit_events")
    assert (audit.source, audit.target) == (1, 1)

    pg_store = SecurityStore(scratch_pg_url)  # type: ignore[arg-type]
    events = pg_store.get_all_audit_events_ordered()
    assert [e.event_id for e in events] == ["e1"]
    nxt = pg_store.append_audit_event(
        event_id="e2", timestamp=2.0, tenant_id="t", subject_id="s", action="a", resource="r",
        decision="allow", reason_code="ok", prev_hash="h1", event_hash="h2", signature="sig",
    )
    assert nxt.sequence_id == 2  # serial sequence re-seated after the copy


def test_copy_rejects_wrong_url_kinds(tmp_path):
    with pytest.raises(ValueError):
        copy_database("postgresql://u@h/db", "postgresql://u@h/db")
    with pytest.raises(ValueError):
        copy_database(f"sqlite:///{tmp_path / 'x.db'}", f"sqlite:///{tmp_path / 'y.db'}")
