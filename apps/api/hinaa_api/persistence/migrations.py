from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Table,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Engine

from .orm import (
    AgentEventRecord,
    AgentPlanRecord,
    AgentRunRecord,
    AgentStepRecord,
    Base,
    MessageAttachment,
    ProviderUsage,
)

logger = logging.getLogger(__name__)

MIGRATIONS_TABLE_NAME = "schema_migrations"


def get_schema_migrations_table(metadata=Base.metadata) -> Table:
    if MIGRATIONS_TABLE_NAME in metadata.tables:
        return metadata.tables[MIGRATIONS_TABLE_NAME]
    return Table(
        MIGRATIONS_TABLE_NAME,
        metadata,
        Column("version", String(64), primary_key=True),
        Column("name", String(255), nullable=False),
        Column("applied_at", DateTime(timezone=True), nullable=False),
    )


def ensure_migrations_table(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(MIGRATIONS_TABLE_NAME):
        table = get_schema_migrations_table()
        table.create(engine, checkfirst=True)
        logger.info("Created schema migrations table: %s", MIGRATIONS_TABLE_NAME)


def _migration_0001_initial_schema(engine: Engine) -> None:
    """Creates base tables if not present."""
    Base.metadata.create_all(engine)


def _migration_0002_explicit_memories_expires_at(engine: Engine) -> None:
    """Adds expires_at to explicit_memories if column is absent."""
    inspector = inspect(engine)
    if inspector.has_table("explicit_memories"):
        cols = [c["name"] for c in inspector.get_columns("explicit_memories")]
        if "expires_at" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE explicit_memories ADD COLUMN expires_at DATETIME;"))
            logger.info("Applied migration: added expires_at to explicit_memories")


def _migration_0003_agent_runtime_tables(engine: Engine) -> None:
    """Ensures agent_runs, agent_plans, agent_plan_steps, and agent_events tables exist."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    agent_tables = [
        ("agent_runs", AgentRunRecord.__table__),
        ("agent_plans", AgentPlanRecord.__table__),
        ("agent_plan_steps", AgentStepRecord.__table__),
        ("agent_events", AgentEventRecord.__table__),
    ]
    for table_name, table in agent_tables:
        if table_name not in existing_tables:
            table.create(engine, checkfirst=True)
            logger.info("Applied migration: created table %s", table_name)


def _migration_0004_message_attachments_and_provider_usage(engine: Engine) -> None:
    """Creates message_attachments and provider_usage tables if not present."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    new_tables = [
        ("message_attachments", MessageAttachment.__table__),
        ("provider_usage", ProviderUsage.__table__),
    ]
    for table_name, table in new_tables:
        if table_name not in existing_tables:
            table.create(engine, checkfirst=True)
            logger.info("Applied migration: created table %s", table_name)


MIGRATIONS: list[tuple[str, str, Callable[[Engine], None]]] = [
    ("0001", "initial_schema", _migration_0001_initial_schema),
    ("0002", "explicit_memories_expires_at", _migration_0002_explicit_memories_expires_at),
    ("0003", "agent_runtime_tables", _migration_0003_agent_runtime_tables),
    ("0004", "message_attachments_and_provider_usage", _migration_0004_message_attachments_and_provider_usage),
]


def run_migrations(engine: Engine) -> list[str]:
    """Execute any unapplied migrations in ascending version order."""
    ensure_migrations_table(engine)

    table = get_schema_migrations_table()
    with engine.connect() as conn:
        result = conn.execute(select(table.c.version))
        applied_versions = {row[0] for row in result.fetchall()}

    applied: list[str] = []
    for version, name, migration_fn in MIGRATIONS:
        if version not in applied_versions:
            logger.info("Executing migration %s: %s", version, name)
            migration_fn(engine)
            with engine.begin() as conn:
                conn.execute(
                    table.insert().values(
                        version=version,
                        name=name,
                        applied_at=datetime.now(timezone.utc),
                    )
                )
            applied.append(version)
            logger.info("Migration %s (%s) applied successfully", version, name)

    return applied


def get_migration_status(engine: Engine) -> dict:
    ensure_migrations_table(engine)
    table = get_schema_migrations_table()
    with engine.connect() as conn:
        result = conn.execute(select(table.c.version, table.c.name, table.c.applied_at))
        rows = result.fetchall()
        applied = [
            {"version": r[0], "name": r[1], "applied_at": r[2].isoformat() if r[2] else None}
            for r in rows
        ]
    applied_set = {r["version"] for r in applied}
    pending = [
        {"version": v, "name": n}
        for v, n, _ in MIGRATIONS
        if v not in applied_set
    ]
    return {
        "applied": applied,
        "pending": pending,
        "current_version": MIGRATIONS[-1][0] if MIGRATIONS else None,
    }
