# ADR-004: WebSocket application events with optional WebRTC

## Status
Accepted — 2026-07-30

## Context and purpose
Need bidirectional partial text/audio, cancellation, fallback and debugging.

## Decision
Versioned WebSocket control/event protocol and binary chunks for cascade; optional ephemeral WebRTC direct to capable providers.

## Alternatives considered
SSE is one-way; WebRTC-only raises signaling/debugging complexity; polling misses latency targets.

## Reasoning
WebSocket fits application semantics while WebRTC remains available for direct media latency.

## Risks and consequences
Reconnect/order/backpressure complexity; addressed by sequences, replay cursor, dedupe and limits.

## Acceptance criteria / revisit
Chaos tests converge after duplicate/gap/reconnect. Revisit binary media transport if measured overhead breaks targets.

