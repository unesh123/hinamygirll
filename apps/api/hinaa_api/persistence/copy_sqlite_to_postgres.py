"""Copy a local SQLite Hinaa database into Postgres.

    python -m hinaa_api.persistence.copy_sqlite_to_postgres \\
        --from sqlite:///C:/Users/me/.hinaa/hinaa.db \\
        --to postgresql+psycopg://user:pass@host/db \\
        [--runtime-db path/to/hinaa_autopilot.db ...]

* Schema is created on the target first (the same ordered migrations the API runs).
* Rows are inserted with ``ON CONFLICT DO NOTHING``, so the tool is idempotent and
  safe to re-run; existing target rows are never overwritten.
* Every table's source row count is compared with the target afterwards and the
  process exits non-zero on any shortfall.
* ``--runtime-db`` copies the standalone SQLite files used by the autopilot, goals,
  security-audit and agent task/event stores into the target's ``hinaa_runtime``
  schema (tables are created by instantiating those stores against the target).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Integer, Table, inspect, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from . import sqlcompat
from .db import is_postgres_url, make_engine, normalize_database_url
from .migrations import run_migrations
from .orm import Base

BATCH_SIZE = 500
_SKIP_TABLES = {"schema_migrations", "alembic_version"}


@dataclass
class TableResult:
    table: str
    source: int
    target: int

    @property
    def ok(self) -> bool:
        return self.target >= self.source


def _count(conn, table: Table) -> int:  # type: ignore[no-untyped-def]
    return int(conn.execute(select(text("count(*)")).select_from(table)).scalar_one())


def copy_orm_tables(source: Engine, target: Engine) -> list[TableResult]:
    """Copy every SQLAlchemy-managed table the source has, in FK order."""
    source_tables = set(inspect(source).get_table_names())
    results: list[TableResult] = []
    for table in Base.metadata.sorted_tables:
        if table.name in _SKIP_TABLES or table.name not in source_tables:
            continue
        source_columns = {c["name"] for c in inspect(source).get_columns(table.name)}
        columns = [c for c in table.columns if c.name in source_columns]
        if not columns:
            continue
        with source.connect() as src, target.begin() as dst:
            result = src.execute(select(*columns))
            while True:
                rows = result.mappings().fetchmany(BATCH_SIZE)
                if not rows:
                    break
                dst.execute(pg_insert(table).on_conflict_do_nothing(), [dict(r) for r in rows])
        with source.connect() as src, target.connect() as dst:
            results.append(TableResult(table.name, _count(src, table), _count(dst, table)))
        _reset_sequences(target, table)
    return results


def _reset_sequences(target: Engine, table: Table) -> None:
    """Re-seat serial sequences after explicit-id inserts."""
    for column in table.primary_key.columns:
        if isinstance(column.type, Integer) and column.autoincrement is not False:
            with target.begin() as conn:
                conn.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence(:t, :c), "
                        "COALESCE((SELECT MAX(" + column.name + ") FROM " + table.name + "), 1), "
                        "(SELECT COUNT(*) FROM " + table.name + ") > 0) "
                        "WHERE pg_get_serial_sequence(:t, :c) IS NOT NULL"
                    ),
                    {"t": table.name, "c": column.name},
                )


def _ensure_runtime_tables(target_url: str) -> None:
    from ..agents.event_log import EventLogStore
    from ..agents.resume import TaskStore
    from ..autopilot.store import AutopilotStore
    from ..goals.store import GoalStore
    from ..memory.repository import MemoryRepository
    from ..security.store import SecurityStore

    AutopilotStore(db_path=target_url)
    GoalStore(db_path=target_url)
    SecurityStore(db_path=target_url)  # type: ignore[arg-type]
    TaskStore(db_path=target_url)
    EventLogStore(db_path=target_url)
    MemoryRepository(db_path=target_url)


def copy_runtime_db(sqlite_path: Path, target_url: str) -> list[TableResult]:
    """Copy all tables of a standalone SQLite store file into the runtime schema."""
    results: list[TableResult] = []
    src = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlcompat.connect_pg(target_url)
    try:
        tables = [
            r[0]
            for r in src.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for name in tables:
            dest_columns = {
                r[0]
                for r in dst.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = ? AND table_name = ?",
                    (sqlcompat.RUNTIME_SCHEMA, name),
                )
            }
            if not dest_columns:
                continue  # e.g. SQLite-only FTS shadow tables
            cols = [r[1] for r in src.execute(f'PRAGMA table_info("{name}")') if r[1] in dest_columns]
            if not cols:
                continue
            col_list = ", ".join(f'"{c}"' for c in cols)
            insert_sql = (
                f'INSERT INTO "{name}" ({col_list}) VALUES ({", ".join("?" for _ in cols)}) '
                "ON CONFLICT DO NOTHING"
            )
            batch: list[tuple] = []
            for row in src.execute(f'SELECT {col_list} FROM "{name}"'):
                batch.append(tuple(row))
                if len(batch) >= BATCH_SIZE:
                    dst.executemany(insert_sql, batch)
                    batch.clear()
            if batch:
                dst.executemany(insert_sql, batch)
            dst.commit()
            for r in dst.execute(
                "SELECT a.attname, pg_get_serial_sequence(?, a.attname) FROM pg_attribute a "
                "WHERE a.attrelid = ?::regclass AND a.attnum > 0 AND NOT a.attisdropped",
                (f"{sqlcompat.RUNTIME_SCHEMA}.{name}", f"{sqlcompat.RUNTIME_SCHEMA}.{name}"),
            ).fetchall():
                if r[1]:
                    dst.execute(
                        f"SELECT setval('{r[1]}', COALESCE((SELECT MAX({r[0]}) FROM {name}), 1), "
                        f"(SELECT COUNT(*) FROM {name}) > 0)"
                    )
            dst.commit()
            n_src = src.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            n_dst = dst.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            results.append(TableResult(f"{sqlcompat.RUNTIME_SCHEMA}.{name}", n_src, n_dst))
    finally:
        src.close()
        dst.close()
    return results


def copy_database(
    source_url: str, target_url: str, runtime_dbs: Sequence[Path] = ()
) -> list[TableResult]:
    source_url = normalize_database_url(source_url)
    target_url = normalize_database_url(target_url)
    if not source_url.startswith("sqlite"):
        raise ValueError("--from must be a sqlite:/// URL")
    if not is_postgres_url(target_url):
        raise ValueError("--to must be a postgresql+psycopg:// URL")
    source = make_engine(source_url)
    target = make_engine(target_url)
    try:
        run_migrations(target)
        results = copy_orm_tables(source, target)
        if runtime_dbs:
            _ensure_runtime_tables(target_url)
            for path in runtime_dbs:
                results.extend(copy_runtime_db(Path(path), target_url))
        return results
    finally:
        source.dispose()
        target.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--from", dest="source", required=True, help="sqlite:///path/to/hinaa.db")
    parser.add_argument("--to", dest="target", required=True, help="postgresql+psycopg://user:pass@host/db")
    parser.add_argument(
        "--runtime-db",
        action="append",
        default=[],
        type=Path,
        help="standalone store SQLite file (hinaa_autopilot.db, hinaa_agent_tasks.db, ...); repeatable",
    )
    args = parser.parse_args(argv)
    try:
        results = copy_database(args.source, args.target, args.runtime_db)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    width = max((len(r.table) for r in results), default=10)
    bad = 0
    for r in results:
        flag = "ok" if r.ok else "MISMATCH"
        bad += not r.ok
        print(f"{r.table:<{width}}  source={r.source:<8} target={r.target:<8} {flag}")
    print(f"{len(results)} tables, {sum(r.source for r in results)} source rows, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
