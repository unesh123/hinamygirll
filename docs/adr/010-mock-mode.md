# ADR-010: Deterministic zero-key mock mode

## Status
Accepted — 2026-07-30

## Context and purpose
UI, avatar, offline demo and CI cannot depend on paid/available providers.

## Decision
All provider ports have deterministic fixture-backed mock adapters that simulate streaming, latency, errors, emotion and audio timing using redistributable local assets.

## Alternatives considered
Record/replay real vendor responses may leak/carry restrictive terms; always-online tests are flaky and costly.

## Reasoning
Mock mode makes Phase 1 useful before credentials and guarantees demo fallback.

## Risks and consequences
Mocks can diverge. Shared contracts and periodic conformance runs limit drift.

## Acceptance criteria / revisit
Fresh clone completes full mock turn offline/no keys; fixtures pass schemas and licences.

