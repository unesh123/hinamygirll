# ADR-007: Explicit long-term memory

## Status
Accepted — 2026-07-30

## Context and purpose
Personalization must not silently retain sensitive conversation.

## Decision
Long-term memories require explicit command or confirmation; private sessions disable persistence; CRUD/delete/export are first-class.

## Alternatives considered
Automatic extraction is smoother but increases surprise, errors and harm. No memory loses a core requested feature.

## Reasoning
Consent preserves agency and creates a clear academic/security test.

## Risks and consequences
More prompts and lower recall. Candidate chips and duplicate assistance reduce friction.

## Acceptance criteria / revisit
No write without consent event; deletion and RLS tests pass. Automatic low-risk memory may be researched only post-MVP with separate consent.

