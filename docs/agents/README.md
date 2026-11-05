# HINAA OS — Multi-Agent Swarms & Autonomous Tooling (`apps/api/hinaa_api/agents/`)

This package provides the core orchestration engine for HINAA OS multi-agent swarms, DAG planning, and cryptographic governance.

## Architecture & Modules

- `contracts.py`: Authoritative typed data models (`AgentRole`, `TaskStatus`, `PermissionTier`, `TaskNode`, `TaskSpec`, `ToolReceipt`, `ApprovalRecord`, `BudgetLedger`).
- `registry.py`: Canonical catalog of 10 specialist roles, least-privilege capability grants, and provider degradation handling.
- `planner.py`: Directed Acyclic Graph (DAG) generation, topological dependency sorting, and cycle detection (`DAGCycleError`).
- `handoff.py`: Minimized context handoff packets, secret token scrubbing (`ContextScrubber`), and bounded delegation depth.
- `verifier.py`: Independent postcondition oracle validating physical exit codes, SHA-256 artifact hashes, and resolving agent conflicts.
- `resume.py`: SQLite WAL persistence (`hinaa_agent_tasks.db`), Compare-and-Swap (CAS) worker leases, and crash restart recovery.
- `dispatcher.py`: Single-agent fast path vs multi-agent swarm decision gate, bounded concurrency queue (max 5 concurrent tasks).
- `budget.py`: Token quotas, integer paisa monetary bounds, tool call quotas, and wall-clock execution deadlines.
- `policy_bridge.py`: HMAC-SHA256 one-time-use approval tokens, argument digest verification, and emergency stop kill-switch.
- `event_log.py`: Append-only event store (`hinaa_agent_events.db`) with monotonic sequence numbers and cursor-based SSE streams.
- `supervisor.py`: Authoritative mission coordinator and execution engine.
- `reflection.py`: Continuous learning extractor staging candidates into the Phase 10 quarantine.
- `service.py`: Unified `AgentOrchestrationService` facade and global singleton `agent_service`.

## REST API Endpoints

- `POST /api/agents/tasks`: Create and plan a new task with DAG.
- `GET /api/agents/tasks/{id}`: Inspect task and node statuses.
- `POST /api/agents/tasks/{id}/run`: Run task to completion or next approval gate.
- `GET /api/agents/tasks/{id}/events`: Stream real-time events via SSE (`text/event-stream`).
- `POST /api/agents/tasks/{id}/approve`: Cryptographically authorize a pending Tier C action.
- `POST /api/agents/tasks/{id}/cancel`: Cancel a task and release worker leases.
- `POST /api/agents/tasks/{id}/resume`: Resume interrupted tasks after restart.
- `GET /api/agents/tasks/{id}/artifacts`: List verified physical artifacts and SHA-256 hashes.
- `GET /api/agents/registry`: Enumerate available specialist specifications and granted capabilities.
- `GET /api/agents/health`: Return orchestration vitals, concurrency meters, and emergency stop status.
