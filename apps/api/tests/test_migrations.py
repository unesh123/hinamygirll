from __future__ import annotations

import pytest
from sqlalchemy import Column, String, Table, inspect, select, text
from sqlalchemy.orm import Session

from hinaa_api.config import Settings
from hinaa_api.persistence.db import init_db, make_engine
from hinaa_api.persistence.migrations import (
    MIGRATIONS_TABLE_NAME,
    get_migration_status,
    run_migrations,
)
from hinaa_api.persistence.orm import (
    AgentEventRecord,
    AgentPlanRecord,
    AgentRunRecord,
    AgentStepRecord,
    Base,
)


def test_migrations_fresh_database():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    applied = run_migrations(engine)
    assert applied == ["0001", "0002", "0003", "0004"]

    status = get_migration_status(engine)
    assert len(status["applied"]) == 4
    assert len(status["pending"]) == 0
    assert status["current_version"] == "0004"

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert MIGRATIONS_TABLE_NAME in tables
    assert "agent_runs" in tables
    assert "agent_plans" in tables
    assert "agent_plan_steps" in tables
    assert "agent_events" in tables
    assert "explicit_memories" in tables
    assert "message_attachments" in tables
    assert "provider_usage" in tables

    # Verify expires_at column on explicit_memories
    cols = [c["name"] for c in inspector.get_columns("explicit_memories")]
    assert "expires_at" in cols


def test_migrations_idempotency():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    applied_first = run_migrations(engine)
    assert len(applied_first) == 4

    applied_second = run_migrations(engine)
    assert applied_second == []

    status = get_migration_status(engine)
    assert len(status["applied"]) == 4
    assert len(status["pending"]) == 0


def test_migrations_upgrade_legacy_database():
    engine = make_engine("sqlite+pysqlite:///:memory:")

    # Simulate legacy database: only create non-agent tables, and without expires_at
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                auth_subject VARCHAR(200) UNIQUE,
                status VARCHAR(40),
                memory_enabled BOOLEAN,
                created_at DATETIME,
                deleted_at DATETIME
            )
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE explicit_memories (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36),
                category VARCHAR(50),
                content TEXT,
                confidence FLOAT,
                source_turn_ref VARCHAR(100),
                created_at DATETIME,
                deleted_at DATETIME
            )
        """
            )
        )

    # Verify legacy state
    inspector = inspect(engine)
    initial_tables = inspector.get_table_names()
    assert "agent_runs" not in initial_tables
    assert "expires_at" not in [c["name"] for c in inspector.get_columns("explicit_memories")]

    # Run migrations
    applied = run_migrations(engine)
    assert "0001" in applied
    assert "0002" in applied
    assert "0003" in applied

    # Verify post-migration state
    inspector = inspect(engine)
    upgraded_tables = inspector.get_table_names()
    assert "agent_runs" in upgraded_tables
    assert "agent_plans" in upgraded_tables
    assert "agent_plan_steps" in upgraded_tables
    assert "agent_events" in upgraded_tables
    assert "expires_at" in [c["name"] for c in inspector.get_columns("explicit_memories")]


def test_init_db_automatically_runs_migrations():
    settings = Settings(
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
    )
    factory = init_db(settings)
    with factory() as session:
        # Check that we can insert an agent run into the migrated database
        run = AgentRunRecord(
            run_id="migrated_run_1",
            user_id="user_test",
            goal="test migration init",
            status="queued",
        )
        session.add(run)
        session.commit()

        retrieved = session.get(AgentRunRecord, "migrated_run_1")
        assert retrieved is not None
        assert retrieved.goal == "test migration init"
