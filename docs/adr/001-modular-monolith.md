# ADR-001: FastAPI modular monolith

## Status
Accepted — 2026-07-30

## Context and purpose
One student, 16 weeks, <=20 concurrent demo sessions, but clear provider/memory/realtime boundaries.

## Decision
Deploy one FastAPI process/container with internal modules and provider ports. PostgreSQL is shared with module-owned tables. No service mesh/message broker.

## Alternatives considered
Microservices allow independent scaling; serverless functions simplify isolated endpoints; both complicate sockets, local work and observability.

## Reasoning
One deployment and transaction boundary is achievable while interfaces permit later extraction.

## Risks and consequences
A failing module can affect all requests and scaling is coarse. Isolate provider calls with timeouts/circuits and measure before extraction.

## Acceptance criteria / revisit
Module dependency tests pass. Revisit only with sustained independent scaling, >10-person team, or reliability boundaries proven by pilot data.

