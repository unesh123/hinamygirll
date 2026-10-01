# ADR 001: Frontier Codex Harness & Operating Core Implementation

**Status**: Accepted  
**Date**: 2026-10-01  
**Architect**: HINAA Core Engineering  

## Context
Following rigorous analysis of OpenAI Codex Core (`codex-rs/core/src/thread_manager.rs`), public GHSA-w5fx-fh39-j5rw security advisories, multi-agent graph schemas, and harness engineering documentation, HINAA required an architectural transformation from an assistant application into a complete cognitive operating environment.

## Decisions

1. **Separation of Cognition and Environment State**:
   - `MODEL STATE != ENVIRONMENT STATE`.
   - `EnvironmentState` models `cwd`, `workspace_roots`, `network_policy`, `shell_runtime`, and process tracking independently of LLM reasoning tokens.

2. **Mitigation of CVE-2025-59532 / GHSA-w5fx-fh39-j5rw**:
   - Model-generated paths or `cwd` arguments MUST NEVER establish the trusted security boundary.
   - All filesystem operations are canonicalized with `os.path.realpath(os.path.abspath(...))` and checked for strict containment within designated `workspace_roots`.

3. **Persistent Multi-Agent Graphs & Message Board**:
   - Introduced `AgentScheduler` with configurable `max_depth` (default 4) and `max_concurrency` (default 6) to eliminate infinite recursive agent spawning.
   - `LocalAgentMessageBoard` provides typed asynchronous communication (`task_assignment`, `status_update`, `followup_task`, `critic_feedback`).
   - Cascading subtree cancellation ensures stopping a parent cleanly terminates all downstream subagents.

4. **Repository-as-Memory (`.hina/`)**:
   - Knowledge is maintained inside versioned, machine-verifiable markdown files:
     - `.hina/architecture.md`
     - `.hina/project.md`
     - `.hina/conventions.md`
     - `.hina/quality.md`
     - `.hina/security.md`
     - `.hina/active-plan.md`
     - `.hina/decisions/`
   - Compiled directly into cache-friendly prompt prefixes.

5. **Protocol-Level Context Compaction**:
   - Implemented `CompactionWorker` to compress historical turns when token thresholds (75%) are reached while preserving open goals, machine state, and opaque reasoning continuity.

6. **Autonomous Verifier Brain**:
   - `planner -> worker -> verifier -> repair` loop enforcing AST parsing, credential stripping, and speech purity.

## Consequences
HINAA now possesses the foundational primitives of an autonomous AI software engineering organization.
