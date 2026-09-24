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
    ConversationEpisode,
    ConversationEntity,
    DurableDeadLetter,
    DurableInboxEvent,
    DurableOutboxEvent,
    DurableTask,
    DurableTaskCheckpoint,
    DurableTaskEvent,
    DurableTaskStep,
    EpisodicMemory,
    MessageAttachment,
    ProviderUsage,
    SideEffectJournal,
    TrainingExampleCandidate,
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


def _migration_0005_conversation_intelligence_tables(engine: Engine) -> None:
    """Creates persistent entity and episodic memory tables if absent."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    new_tables = [
        ("conversation_entities", ConversationEntity.__table__),
        ("episodic_memories", EpisodicMemory.__table__),
    ]
    for table_name, table in new_tables:
        if table_name not in existing_tables:
            table.create(engine, checkfirst=True)
            logger.info("Applied migration: created table %s", table_name)


def _migration_0006_training_candidate_table(engine: Engine) -> None:
    """Creates reviewed-offline training candidate table if absent."""
    inspector = inspect(engine)
    if "training_example_candidates" not in set(inspector.get_table_names()):
        TrainingExampleCandidate.__table__.create(engine, checkfirst=True)
        logger.info("Applied migration: created table training_example_candidates")


def _migration_0007_durable_task_tables(engine: Engine) -> None:
    """Creates durable task/checkpoint/event tables if absent."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    new_tables = [
        ("durable_tasks", DurableTask.__table__),
        ("durable_task_steps", DurableTaskStep.__table__),
        ("durable_task_checkpoints", DurableTaskCheckpoint.__table__),
        ("durable_task_events", DurableTaskEvent.__table__),
    ]
    for table_name, table in new_tables:
        if table_name not in existing_tables:
            table.create(engine, checkfirst=True)
            logger.info("Applied migration: created table %s", table_name)


def _migration_0008_user_continuity_state(engine: Engine) -> None:
    """Creates user_continuity_states and adds cross-session scoping columns."""
    from .orm import UserContinuityState
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "user_continuity_states" not in existing_tables:
        UserContinuityState.__table__.create(engine, checkfirst=True)
        logger.info("Applied migration: created table user_continuity_states")

    with engine.begin() as conn:
        if "explicit_memories" in existing_tables:
            cols = [c["name"] for c in inspector.get_columns("explicit_memories")]
            if "scope" not in cols:
                conn.execute(text("ALTER TABLE explicit_memories ADD COLUMN scope VARCHAR(40) DEFAULT 'user_global';"))
            if "project_id" not in cols:
                conn.execute(text("ALTER TABLE explicit_memories ADD COLUMN project_id VARCHAR(36);"))
            if "entity_id" not in cols:
                conn.execute(text("ALTER TABLE explicit_memories ADD COLUMN entity_id VARCHAR(100);"))
            if "superseded_by_id" not in cols:
                conn.execute(text("ALTER TABLE explicit_memories ADD COLUMN superseded_by_id VARCHAR(36);"))

        if "episodic_memories" in existing_tables:
            cols = [c["name"] for c in inspector.get_columns("episodic_memories")]
            if "project_id" not in cols:
                conn.execute(text("ALTER TABLE episodic_memories ADD COLUMN project_id VARCHAR(36);"))
            if "scope" not in cols:
                conn.execute(text("ALTER TABLE episodic_memories ADD COLUMN scope VARCHAR(40) DEFAULT 'conversation';"))

        if "conversation_summaries" in existing_tables:
            cols = [c["name"] for c in inspector.get_columns("conversation_summaries")]
            if "topics_json" not in cols:
                conn.execute(text("ALTER TABLE conversation_summaries ADD COLUMN topics_json TEXT DEFAULT '[]';"))
            if "entities_json" not in cols:
                conn.execute(text("ALTER TABLE conversation_summaries ADD COLUMN entities_json TEXT DEFAULT '[]';"))
            if "decisions_json" not in cols:
                conn.execute(text("ALTER TABLE conversation_summaries ADD COLUMN decisions_json TEXT DEFAULT '[]';"))


def _migration_0009_conversation_turn_states(engine: Engine) -> None:
    """Creates conversation_turn_states table if absent."""
    from .orm import ConversationTurnState
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "conversation_turn_states" not in existing_tables:
        ConversationTurnState.__table__.create(engine, checkfirst=True)
        logger.info("Applied migration: created table conversation_turn_states")


def _migration_0010_conversation_turn_state_active_goal(engine: Engine) -> None:
    """Adds active_goal_json column to conversation_turn_states if absent."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "conversation_turn_states" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("conversation_turn_states")}
        if "active_goal_json" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE conversation_turn_states ADD COLUMN active_goal_json TEXT;"))
                logger.info("Applied migration: added active_goal_json column to conversation_turn_states")


def _migration_0011_task_runtime_hardening(engine: Engine) -> None:
    """Adds lease/fencing/versioning, side-effect journal, outbox/inbox, and DLQ primitives."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if "durable_tasks" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("durable_tasks")}
        statements = []
        if "version" not in cols:
            statements.append("ALTER TABLE durable_tasks ADD COLUMN version INTEGER DEFAULT 1;")
        if "worker_id" not in cols:
            statements.append("ALTER TABLE durable_tasks ADD COLUMN worker_id VARCHAR(120);")
        if "lease_id" not in cols:
            statements.append("ALTER TABLE durable_tasks ADD COLUMN lease_id VARCHAR(64);")
        if "fencing_token" not in cols:
            statements.append("ALTER TABLE durable_tasks ADD COLUMN fencing_token INTEGER DEFAULT 0;")
        if "lease_acquired_at" not in cols:
            statements.append("ALTER TABLE durable_tasks ADD COLUMN lease_acquired_at DATETIME;")
        if "lease_expires_at" not in cols:
            statements.append("ALTER TABLE durable_tasks ADD COLUMN lease_expires_at DATETIME;")
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))

    if "durable_task_steps" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("durable_task_steps")}
        statements = []
        if "version" not in cols:
            statements.append("ALTER TABLE durable_task_steps ADD COLUMN version INTEGER DEFAULT 1;")
        if "max_attempts" not in cols:
            statements.append("ALTER TABLE durable_task_steps ADD COLUMN max_attempts INTEGER DEFAULT 3;")
        if "retry_after" not in cols:
            statements.append("ALTER TABLE durable_task_steps ADD COLUMN retry_after DATETIME;")
        if "deadline_at" not in cols:
            statements.append("ALTER TABLE durable_task_steps ADD COLUMN deadline_at DATETIME;")
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))

    new_tables = [
        ("side_effect_journal", SideEffectJournal.__table__),
        ("durable_outbox_events", DurableOutboxEvent.__table__),
        ("durable_inbox_events", DurableInboxEvent.__table__),
        ("durable_dead_letters", DurableDeadLetter.__table__),
    ]
    existing_tables = set(inspector.get_table_names())
    for table_name, table in new_tables:
        if table_name not in existing_tables:
            table.create(engine, checkfirst=True)
            logger.info("Applied migration: created table %s", table_name)


def _migration_0012_selected_asset_state(engine: Engine) -> None:
    """Adds exact selected-asset state to conversation_turn_states if absent."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "conversation_turn_states" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("conversation_turn_states")}
        if "selected_asset_json" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE conversation_turn_states ADD COLUMN selected_asset_json TEXT;"))
                logger.info("Applied migration: added selected_asset_json column to conversation_turn_states")


def _migration_0013_conversation_episodes(engine: Engine) -> None:
    """B2 summary tree (§17): creates the conversation_episodes table."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "conversation_episodes" not in existing_tables:
        ConversationEpisode.__table__.create(engine, checkfirst=True)
        logger.info("Applied migration: created table conversation_episodes")


def _migration_0014_reminders(engine: Engine) -> None:
    """Creates the reminders table so a set reminder outlives the process that set it."""
    from .orm import Reminder

    inspector = inspect(engine)
    if "reminders" not in set(inspector.get_table_names()):
        Reminder.__table__.create(engine, checkfirst=True)
        logger.info("Applied migration: created table reminders")


MIGRATIONS: list[tuple[str, str, Callable[[Engine], None]]] = [
    ("0001", "initial_schema", _migration_0001_initial_schema),
    ("0002", "explicit_memories_expires_at", _migration_0002_explicit_memories_expires_at),
    ("0003", "agent_runtime_tables", _migration_0003_agent_runtime_tables),
    ("0004", "message_attachments_and_provider_usage", _migration_0004_message_attachments_and_provider_usage),
    ("0005", "conversation_intelligence_tables", _migration_0005_conversation_intelligence_tables),
    ("0006", "training_candidate_table", _migration_0006_training_candidate_table),
    ("0007", "durable_task_tables", _migration_0007_durable_task_tables),
    ("0008", "user_continuity_state", _migration_0008_user_continuity_state),
    ("0009", "conversation_turn_states", _migration_0009_conversation_turn_states),
    ("0010", "conversation_turn_state_active_goal", _migration_0010_conversation_turn_state_active_goal),
    ("0011", "task_runtime_hardening", _migration_0011_task_runtime_hardening),
    ("0012", "selected_asset_state", _migration_0012_selected_asset_state),
    ("0013", "conversation_episodes", _migration_0013_conversation_episodes),
    ("0014", "reminders", _migration_0014_reminders),
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
