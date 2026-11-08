"""Dialect shim so the raw-SQL stores can run on Postgres as well as SQLite.

The autopilot, goals, security-audit and agent task/event stores speak the
``sqlite3`` DB-API directly. Rather than rewriting ~3k lines of SQL, they obtain
their connection from :func:`connect`, which returns a plain ``sqlite3``
connection for file paths and a thin psycopg-backed adapter for Postgres URLs.

The adapter understands the small SQLite dialect subset these stores use:
``?`` placeholders, ``PRAGMA`` (ignored), ``INTEGER PRIMARY KEY AUTOINCREMENT``,
``REAL``/``BLOB`` column types, ``INSERT OR IGNORE``, ``cursor.lastrowid`` and
``conn.executescript``. ``INSERT OR REPLACE`` is intentionally unsupported.

Tables live in the ``hinaa_runtime`` schema so they cannot collide with the
SQLAlchemy-managed tables (e.g. ``agent_events``) in ``public``.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from collections.abc import Sequence
from typing import Any

from .db import is_postgres_url, normalize_database_url

RUNTIME_SCHEMA = "hinaa_runtime"

_pools: dict[str, Any] = {}
_pools_lock = threading.Lock()
_serial_columns: dict[str, str] = {}

_CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][\w]*)", re.I)
_AUTOINC_RE = re.compile(r"([A-Za-z_]\w*)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", re.I)
_INSERT_RE = re.compile(r"^\s*INSERT\s+(?:OR\s+(IGNORE|REPLACE)\s+)?INTO\s+([A-Za-z_]\w*)", re.I)


def pg_target(db_path: Any, *, is_default: bool) -> str | None:
    """Return a normalised Postgres URL for a store, or None to use SQLite.

    An explicit Postgres URL as ``db_path`` always wins. A store left at its
    default location follows ``HINAA_DATABASE_URL`` so hosted deploys need no
    per-store configuration, while explicit file paths (tests, local tools) keep
    working exactly as before.
    """
    text = str(db_path) if db_path is not None else ""
    if is_postgres_url(text):
        return normalize_database_url(text)
    if is_default:
        env = os.environ.get("HINAA_DATABASE_URL", "")
        if is_postgres_url(env):
            return normalize_database_url(env)
    return None


def _translate(sql: str) -> str | None:
    """Translate SQLite-flavoured SQL to Postgres. None means 'skip statement'."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped or stripped.upper().startswith("PRAGMA"):
        return None
    create = _CREATE_TABLE_RE.match(stripped)
    if create:
        auto = _AUTOINC_RE.search(stripped)
        if auto:
            _serial_columns[create.group(1).lower()] = auto.group(1)
    out = _AUTOINC_RE.sub(r"\1 BIGSERIAL PRIMARY KEY", stripped)
    out = re.sub(r"\bBLOB\b", "BYTEA", out, flags=re.I)
    out = re.sub(r"\bREAL\b", "DOUBLE PRECISION", out, flags=re.I)
    insert = _INSERT_RE.match(out)
    if insert and insert.group(1):
        if insert.group(1).upper() == "REPLACE":
            raise NotImplementedError("INSERT OR REPLACE is not supported on Postgres; use ON CONFLICT")
        out = _INSERT_RE.sub(f"INSERT INTO {insert.group(2)}", out, count=1)
        if "ON CONFLICT" not in out.upper():
            out += " ON CONFLICT DO NOTHING"
    return _convert_placeholders(out)


def _convert_placeholders(sql: str) -> str:
    """Swap ``?`` for ``%s`` outside string literals and escape literal ``%``."""
    out: list[str] = []
    quote: str | None = None
    for ch in sql:
        if quote:
            out.append("%%" if ch == "%" else ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "?":
            out.append("%s")
        elif ch == "%":
            out.append("%%")
        else:
            out.append(ch)
    return "".join(out)


class Row:
    """sqlite3.Row look-alike: index, name, ``keys()`` and iteration."""

    __slots__ = ("_names", "_values")

    def __init__(self, names: Sequence[str], values: Sequence[Any]) -> None:
        self._names = tuple(names)
        self._values = tuple(values)

    def __getitem__(self, key: int | str | slice) -> Any:
        if isinstance(key, str):
            try:
                return self._values[self._names.index(key)]
            except ValueError:
                raise IndexError(f"No item with that key: {key}") from None
        return self._values[key]

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Row) and self._values == other._values and self._names == other._names

    def __hash__(self) -> int:
        return hash(self._values)

    def keys(self) -> list[str]:
        return list(self._names)


def _row_factory(cursor: Any):  # type: ignore[no-untyped-def]
    names = [c.name for c in (cursor.description or [])]
    return lambda values: Row(names, values)


def _get_pool(url: str):  # type: ignore[no-untyped-def]
    with _pools_lock:
        pool = _pools.get(url)
        if pool is None:
            from psycopg.conninfo import make_conninfo
            from psycopg_pool import ConnectionPool
            from sqlalchemy.engine import make_url

            parsed = make_url(url)
            conninfo = make_conninfo(
                host=parsed.host,
                port=parsed.port,
                user=parsed.username,
                password=parsed.password,
                dbname=parsed.database,
                options=f"-c search_path={RUNTIME_SCHEMA},public",
                **{k: v for k, v in parsed.query.items() if isinstance(v, str)},
            )
            pool = ConnectionPool(
                conninfo,
                min_size=1,
                max_size=int(os.environ.get("HINAA_DB_POOL_SIZE", "5") or 5),
                kwargs={"row_factory": _row_factory},
                open=False,
                check=ConnectionPool.check_connection,
            )
            pool.open(wait=True, timeout=30)
            from psycopg import connect as _connect

            with _connect(conninfo, autocommit=True) as boot:
                boot.execute(f"CREATE SCHEMA IF NOT EXISTS {RUNTIME_SCHEMA}")
            _pools[url] = pool
        return pool


class _Cursor:
    def __init__(self, cur: Any, lastrowid: int | None = None) -> None:
        self._cur = cur
        self.lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount if self._cur is not None else 0

    @property
    def description(self) -> Any:
        return self._cur.description if self._cur is not None else None

    def fetchone(self) -> Row | None:
        return self._cur.fetchone() if self._cur is not None and self._cur.description else None

    def fetchall(self) -> list[Row]:
        return self._cur.fetchall() if self._cur is not None and self._cur.description else []

    def fetchmany(self, size: int = 1) -> list[Row]:
        return self._cur.fetchmany(size) if self._cur is not None and self._cur.description else []

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.fetchall())


class _PgCursor:
    """DB-API cursor facade: ``cur.execute(...)`` then ``cur.fetch*()``."""

    def __init__(self, conn: PgConnection) -> None:
        self._conn = conn
        self._last = _Cursor(None)

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> _PgCursor:
        self._last = self._conn.execute(sql, params)
        return self

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> _PgCursor:
        self._last = self._conn.executemany(sql, seq)
        return self

    def __getattr__(self, name: str) -> Any:
        return getattr(self._last, name)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._last)

    def close(self) -> None:
        return None


class PgConnection:
    """sqlite3.Connection-shaped wrapper over a pooled psycopg connection.

    ``with conn:`` commits/rolls back like sqlite3 and does not close. The
    underlying connection returns to the pool on ``close()`` and is re-acquired
    lazily if the wrapper is used again.
    """

    def __init__(self, url: str, *, autocommit: bool = False) -> None:
        self._url = url
        self._autocommit = autocommit
        self._conn: Any = None

    def _acquire(self) -> Any:
        if self._conn is None:
            self._conn = _get_pool(self._url).getconn()
            if self._autocommit:
                self._conn.autocommit = True
        return self._conn

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> _Cursor:
        keyword = sql.strip().rstrip(";").split(None, 1)[0].upper() if sql.strip() else ""
        if not self._autocommit and keyword in ("BEGIN", "COMMIT", "ROLLBACK"):
            # Implicit transactions: psycopg already opened one; map to its API.
            if keyword == "COMMIT":
                self.commit()
            elif keyword == "ROLLBACK":
                self.rollback()
            return _Cursor(None)
        translated = _translate(sql)
        if translated is None:
            return _Cursor(None)
        if self._autocommit and keyword == "BEGIN":
            translated = "BEGIN"
        conn = self._acquire()
        lastrowid: int | None = None
        insert = _INSERT_RE.match(translated.replace("%%", "%"))
        serial = _serial_columns.get(insert.group(2).lower()) if insert else None
        if serial and "RETURNING" not in translated.upper():
            translated += f" RETURNING {serial}"
        else:
            serial = None
        cur = conn.execute(translated, tuple(params) if params is not None else ())
        if serial:
            row = cur.fetchone()
            lastrowid = int(row[0]) if row else None
        return _Cursor(cur, lastrowid)

    def cursor(self) -> _PgCursor:
        return _PgCursor(self)

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> _Cursor:
        last = _Cursor(None)
        for params in seq:
            last = self.execute(sql, params)
        return last

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        if self._conn is not None:
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn is not None:
            self._conn.rollback()

    def close(self) -> None:
        if self._conn is not None:
            conn, self._conn = self._conn, None
            if self._autocommit:
                conn.autocommit = False
            _get_pool(self._url).putconn(conn)

    def __enter__(self) -> PgConnection:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def connect_pg(url: str, *, autocommit: bool = False) -> PgConnection:
    return PgConnection(url, autocommit=autocommit)


def reset_pools() -> None:
    """Close all pooled connections (test isolation / shutdown)."""
    with _pools_lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()


import atexit  # noqa: E402

atexit.register(reset_pools)
