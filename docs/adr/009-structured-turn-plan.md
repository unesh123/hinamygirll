# ADR-009: Structured, allowlisted AssistantTurnPlan

## Status
Accepted — 2026-07-30

## Context and purpose
Models must coordinate text and performance without controlling code/bones/files/tools.

## Decision
Strict JSON Schema with no additional properties and allowlisted emotion, face, gesture, gaze and head motion. Server validates and compiles symbolic cues.

## Alternatives considered
Free-text parsing is fragile; direct animation code is unsafe; client validation alone is bypassable.

## Reasoning
Symbolic plans are portable, testable and safe.

## Risks and consequences
Reduced creativity and occasional invalid output. Use controlled variation in deterministic performance compiler and neutral fallback.

## Acceptance criteria / revisit
Fuzzed invalid plans never reach engine; schema valid rate is measured. Expand allowlists only with licensed assets/tests.

