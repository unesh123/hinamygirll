"""Baseline: run the ordered legacy MIGRATIONS list.

Databases created by the API's startup migrator already have every applied
version recorded in ``schema_migrations``; this revision then performs no DDL and
simply lets Alembic record itself (stamping). Fresh databases get the full chain.
Add future schema changes as new Alembic revisions after this one.

Revision ID: 0001_baseline
Revises:
"""
from hinaa_api.persistence.migrations import run_migrations
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The legacy migrators open their own connections on the engine, so hand
    # them the engine rather than Alembic's transactional connection.
    run_migrations(op.get_bind().engine)


def downgrade() -> None:
    raise NotImplementedError("The legacy baseline cannot be downgraded.")
