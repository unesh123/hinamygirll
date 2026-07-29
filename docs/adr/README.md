# Architecture decision records

## Purpose

Preserve why major HINAA choices were made and when to revisit them.

## Decision

ADRs are immutable after acceptance except status/link corrections. A changed decision adds a superseding ADR.

| ADR | Decision | Status |
|---|---|---|
| [001](001-modular-monolith.md) | modular monolith | accepted |
| [002](002-pwa-first.md) | PWA before native packaging | accepted |
| [003](003-provider-ports-and-hybrid-voice.md) | provider ports + two voice paths | accepted |
| [004](004-websocket-events-optional-webrtc.md) | WebSocket events, optional WebRTC | accepted |
| [005](005-postgresql-pgvector.md) | PostgreSQL + pgvector | accepted |
| [006](006-vrm-browser-engine.md) | Three.js/R3F/three-vrm | accepted |
| [007](007-explicit-memory.md) | explicit long-term memory only | accepted |
| [008](008-server-secrets-and-byok.md) | server secrets + envelope BYOK design | accepted |
| [009](009-structured-turn-plan.md) | allowlisted TurnPlan | accepted |
| [010](010-mock-mode.md) | deterministic zero-key mock | accepted |
| [011](011-azure-gemini-candidate-route.md) | Azure/Gemini as benchmark candidates | proposed |

## Alternatives considered

Decision rationale embedded only in prose is harder to revisit.

## Reasoning

ADRs link choices to constraints and explicit revisit triggers.

## Risks

Records can drift; architecture review checks status and supersession links.

## Acceptance criteria

Major stack/provider/security/data decisions have an ADR before implementation.

