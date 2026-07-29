# Scope and requirements

## Purpose

Create a testable boundary for the final-year MVP.

## Decision

### In the MVP

1. Installable, responsive, safe-area-aware PWA.
2. Female/male VRM switching using licensed temporary models.
3. Text chat plus tap/push-to-talk with partial transcript.
4. Streaming response/audio where provider capability permits.
5. Nepali input/output benchmarked rather than assumed.
6. Explicit states: idle, listening, thinking, speaking, interrupted, offline, error.
7. Blinking, breathing, gaze, head motion, idle, lip-sync, allowlisted emotion/gesture cues.
8. Barge-in that locally stops playback first, then cancels the server turn.
9. Conversation history and opt-in long-term memory controls.
10. Provider configuration/fallback and zero-key deterministic mock mode.
11. High/medium/low/emergency rendering tiers.
12. Camera as a disabled-by-default, visible, single-frame experiment only.
13. Automated tests, a 1,000-utterance evaluation plan, academic study, and live demo.

### Explicitly post-MVP

Capacitor packaging, continuous camera understanding, image generation, BYOK execution, autonomous tools/device control, subscriptions, marketplace, desktop integration, and regional-language expansion.

### Non-functional targets

Local feedback <100 ms; local playback stop <250 ms; partial transcript p50 <700 ms on good network; realtime first audio p50 <=1.5 s/p95 <=3 s; cascade p50 <=2.5 s; 45–60 FPS capable/high, >=30 FPS supported/low. These are measurement targets, not promises.

### Data and privacy requirements

Purpose limitation, explicit consent, per-user authorization, private-session mode, memory CRUD, data export/deletion, redacted telemetry, retention jobs, and no raw provider keys in browser/database logs.

## Alternatives considered

The commercial feature set was considered and rejected for MVP because it prevents credible testing of the core loop. Camera was retained only as an opt-in experiment because it is demonstrable without surveillance.

## Reasoning

The scope supports one student over 12–16 weeks with cut lines: first camera, then provider-direct realtime, then semantic memory can be removed without breaking the core demo.

## Risks

Two characters and two voice paths multiply testing. They share contracts and engine code; only profiles and assets differ.

## Acceptance criteria

All 20 MVP statements in the request have a corresponding row in the [traceability matrix](22-requirements-traceability-matrix.md); no post-MVP feature is required for the final demonstration.

