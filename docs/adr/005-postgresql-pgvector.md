# ADR-005: PostgreSQL with pgvector

## Status
Accepted — 2026-07-30

## Context and purpose
History, consent, audit, usage and user-isolated semantic memory need transactions.

## Decision
Docker PostgreSQL locally; managed PostgreSQL pilot; pgvector in same database. SQLite only deterministic mock tests.

## Alternatives considered
MongoDB offers flexible documents; dedicated vector DB scales retrieval; both add systems and weaker relational controls for MVP.

## Reasoning
Transactions, FK, RLS and vectors in one store minimize operations.

## Risks and consequences
Vector index/tuning and extension availability. Exact search is adequate initially; benchmark indexes later.

## Acceptance criteria / revisit
RLS isolation and migration/restore tests pass. Revisit dedicated vectors above measured PostgreSQL capacity.

