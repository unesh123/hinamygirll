# ADR-012: SQLAlchemy persistence for Phase 5

## Status

Accepted for offline/dev; PostgreSQL production URL via `HINAA_DATABASE_URL`.

## Decision

Use SQLAlchemy 2.0 ORM with `create_all` for local/test bootstrap and Alembic available for forward migrations. Default test database is SQLite (`StaticPool` in-memory). Production should use PostgreSQL.

## Alternatives

- Raw SQL only: higher migration risk for solo MVP
- MongoDB: weaker relational consent constraints (rejected in docs/09)

## Consequences

- pgvector remains optional and deferred
- RLS should be added as PostgreSQL policies before public multi-tenant production
- Dev auth must never be enabled in public production without network controls
