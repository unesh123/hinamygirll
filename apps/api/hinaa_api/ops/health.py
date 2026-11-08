"""Readiness probes: database connectivity and migration status."""
from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text


def _check_database_sync(session_factory: Any) -> dict[str, Any]:
    from ..persistence.migrations import MIGRATIONS_TABLE_NAME, MIGRATIONS

    engine = session_factory.kw["bind"]
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            applied = {r[0] for r in conn.execute(text(f"SELECT version FROM {MIGRATIONS_TABLE_NAME}"))}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    pending = [version for version, _name, _fn in MIGRATIONS if version not in applied]
    return {"ok": not pending, "migrationsPending": pending, "migrationsApplied": len(applied)}


async def check_database(session_factory: Any | None) -> dict[str, Any]:
    """Cheap `SELECT 1` plus a pending-migrations diff, off the event loop."""
    if session_factory is None:
        return {"ok": True, "skipped": "persistence disabled"}
    return await asyncio.to_thread(_check_database_sync, session_factory)
