# 16-week roadmap

## Purpose

Sequence risk reduction and implementation after the approval gate.

## Decision

| Phase / weeks | Deliverables | Dependencies | Main risk / effort | Acceptance and demo checkpoint |
|---|---|---|---|---|
| 0, W1–2 | approve blueprint, licence inventory, 100-item pilot set, device baseline, provider portal checks | supervisor/owner | scope; 2 pw | ADRs accepted; mock walkthrough; no app code before approval |
| 1, W3–4 | PWA shell, VRM loader, female/male switch, base life, states, mock conversation, text-only | approved temporary assets | WebGL/VRM; 2 pw | Android-responsive installable mock demo at >=30 FPS low tier |
| 2, W5–6 | FastAPI skeleton/contracts, text streaming, Azure STT/TTS spike, configured Gemini adapter | official accounts/keys server-side | Nepali quality/quota; 2 pw | 30-sentence voice benchmark and complete cascade turn |
| 3, W7–8 | WebSocket v1, partials, audio chunks, barge-in, fallback/circuit, offline/reconnect | Phase 2 | race/latency; 2 pw | stop <250 ms local; replay/duplicate tests pass |
| 4, W9–10 | TurnPlan validation, emotion/gesture layers, lips, shared clock, 5–10 polished motions | licensed motions | sync/repetition; 2 pw | synchronized ablation prototype; no invalid cue reaches engine |
| 5, W11–12 | PostgreSQL migrations/RLS, history, explicit memory CRUD, privacy dashboard, deletion | auth/DB | leakage; 2 pw | two-user isolation and remember/forget/delete demo |
| 6, W13–14 | 1,000 text items/review, audio subset, provider tests, performance/accessibility/security, cost report | reviewers/participants | recruitment/time; 2 pw | sealed benchmark, low-tier device and report tables |
| 7, W15–16 | deploy demo, backup/restore, final study/report, rehearsal and contingency video/mock | stable build | demo network; 2 pw | scripted live demo plus offline fallback and signed release checklist |

One person-week (pw) means one student’s available project work for a week, not 40 guaranteed hours. Preserve a half-day weekly for report/evidence and one final-week buffer. Cut order if late: camera experiment → direct realtime/WebRTC → semantic vector retrieval → extra gestures; never cut text fallback, consent, mock mode, schema validation or core tests.

### Immediate Phase 1 order after approval

PWA shell → mobile VRM playground → base life and five states → mock provider → text transcript → quality/text fallback. Real provider integration begins only in Phase 2.

### Phase 1 completion evidence — 2026-07-30

Status: **implemented; awaiting review gate approval**.

- `apps/web` contains the installable React/TypeScript/Vite PWA, deterministic local mock provider, strict runtime TurnPlan validator, avatar-engine interface and procedural placeholder.
- Implemented states: idle, listening, thinking, speaking, interrupted and safe error recovery.
- Base-life placeholder performance includes breathing, blinking, gaze, subtle head movement and bounded emotion/gesture CSS cues. The local VRMs remain quarantined and were not loaded.
- Controls include simulated microphone/partial transcript, stop, text composer, transcript, companion profiles, text-only, reduced motion, disabled camera and explicit “no capture/no API key” labels.
- Production PWA build emits manifest/service worker and precaches seven entries. Offline reload passed after first production visit.
- Automated evidence: 14 Vitest unit/component tests and 8 Playwright tests across Pixel 5 and 320×568 profiles. Formatting, lint, TypeScript, schema tests, production build and Phase 0 blueprint validation pass.
- Accepted Phase 1 deviation: no Three.js/VRM runtime was installed because no local avatar is licence-approved. The procedural adapter proves the engine boundary and degradation behavior without weakening the asset gate.

At the Phase 1 checkpoint, Phase 2 was still blocked: real microphone capture, FastAPI, WebSocket, Azure, Gemini, TTS/STT and credentials had not been added.

### Phase 2 implementation evidence — 2026-07-30

Status: **offline implementation complete; stopped at credential and physical-device review gate**.

- Added the FastAPI modular monolith, strict configuration, correlation IDs, typed safe errors, exact local CORS, size/duration limits, bounded session memory, provider ports and deterministic STT/LLM/TTS mocks.
- Added lazy Azure Speech STT/TTS and Gemini structured-output adapters. Official packages, `ne-NP`, `ne-NP-HemkalaNeural` and `ne-NP-SagarNeural` were reverified; no real provider request was made.
- Added explicit browser microphone capture to 16 kHz mono PCM WAV, track/context cleanup, mock/real routing, validated NDJSON text events, TTS playback/stop/replay/mute and analyser-smoothed jaw motion. The Phase 1 no-permission demo remains available.
- Added a Vite same-origin `/api` proxy, a tested PowerShell launcher and a certificate-file-based HTTPS option. Trusted certificate generation/import was not performed because it changes trust stores and requires owner approval; Android microphone success is not claimed.
- Automated offline evidence: 12 backend tests, 19 frontend tests and 10 Pixel 5/320×568 E2E tests, including backend proxy and missing-credential behavior. Full final gate is recorded in [Phase 2 review](24-phase-2-review.md).

Phase 3 remains blocked. Partial STT, WebSocket audio chunks, continuous streaming audio and barge-in are intentionally not implemented.

### Post-MVP

Capacitor, camera/vision, image/diagram generation, secure tools, BYOK, desktop/mobile integrations, subscriptions, marketplace, original commercial characters and additional regional languages.

## Alternatives considered

Provider-first development delays visible risk and makes every UI test paid. Memory before realtime weakens core demo.

## Reasoning

The order retires 3D/device and Nepali speech risks early while maintaining a demonstrable mock build.

## Risks

Asset/reviewer/provider delays. Use quarantined placeholders only after licence verification, synthetic audio fixtures, and mock adapters.

## Acceptance criteria

Each phase ends with a demo and evidence artifact; no phase proceeds with unresolved critical security/licence gate.
