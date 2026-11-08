"""Alembic environment for Hinaa.

The database URL comes from ``-x url=...`` or ``HINAA_DATABASE_URL`` (same
resolution as the API), defaulting to the local SQLite file.
"""

from __future__ import annotations

import os

from alembic import context

from hinaa_api.config import DEFAULT_LOCAL_DATABASE_URL
from hinaa_api.persistence.db import make_engine, normalize_database_url
from hinaa_api.persistence.orm import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    override = context.get_x_argument(as_dictionary=True).get("url")
    return normalize_database_url(
        override or os.environ.get("HINAA_DATABASE_URL") or DEFAULT_LOCAL_DATABASE_URL
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
