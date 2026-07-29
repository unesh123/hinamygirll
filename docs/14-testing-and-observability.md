# Testing, evaluation and observability

## Purpose

Define evidence required for technical quality and academic claims.

## Decision

### Test pyramid and gates

- Unit: mood bounds/decay, router score, normalization, consent policy, cue compiler, error mapping.
- Contract: every provider against shared fixtures; JSON Schema and OpenAPI examples; mock always runs.
- Integration: PostgreSQL migrations/RLS, memory consent/deletion, session replay, encrypted credential boundary.
- Realtime: reordered/duplicate/gapped WebSocket events, cancellation races, binary correlation, optional WebRTC disconnect.
- End-to-end: US-01–US-10 on Android viewport, provider-stub latency/failures, offline PWA, text-only.
- Prompt: schema validity, Nepali style, factual uncertainty, dependency/manipulation boundaries, injection corpus.
- Security: IDOR/RLS, CSRF/Origin, SSRF, XSS/Markdown, rate/size limits, secret/log scans, malicious GLTF corpus, BYOK design tests post-MVP.
- Media/UI: Playwright viewports/accessibility, screenshot baselines, WebGL loss, audio autoplay/echo/barge-in, reduced motion.
- Performance/load: frame time/long tasks/memory/model load, 50 then 200 concurrent mock sockets, network/CPU throttling and thermal soak.
- Human evaluation: voice study and avatar ablation from [voice evaluation](07-nepali-voice-evaluation.md).

Release gate: all critical tests pass, no high/critical dependency finding without signed exception, schema compatibility verified, p95 target report generated, and rollback rehearsed. Flaky tests are quarantined with owner/expiry, never silently retried to green.

### Observability

Use structured JSON logs, OpenTelemetry-compatible traces and metrics. Correlate `trace_id,session_id_hash,turn_id,provider_request_id_hash`; never record raw key, audio, camera frame, message/memory text, authorization header or full user ID. Development content logging is off by default and uses synthetic fixtures.

Core metrics: active sessions, turn success/cancel/error, first partial/token/audio histograms, local barge-in, provider latency/error/fallback/circuit, schema invalid rate, WS reconnect/gap, FPS/long tasks/WebGL loss, memory consent/retrieval/delete, crash-free sessions and metered usage/cost. Alerts: budget 50/80/95%, provider failure >10%/5 min, auth/RLS denial anomaly, error spike, deletion-job backlog.

Academic runs write immutable configuration snapshots (not credentials), dataset version, device/network and provider catalog IDs. Operational dashboards must not become research datasets without consent.

## Alternatives considered

Only unit/E2E tests miss contracts and race conditions. Full production telemetry is excessive; a focused RED + client-performance set is sufficient.

## Reasoning

The project’s claims are latency, language accuracy, naturalness and graceful degradation; instrumentation must measure those directly.

## Risks

Telemetry can leak private content and observer overhead can affect audio. Redact at source, sample traces, benchmark with/without instrumentation.

## Acceptance criteria

- Every traceability row names a test.
- Dashboard reports p50/p95 and sample count, not averages alone.
- Redaction tests inject canary secrets/content and find none in outputs.
- Evaluation run is reproducible from versioned configuration.

