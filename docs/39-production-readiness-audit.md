# 39 — Production-readiness audit

Legend: Verified | Partially verified | Blocked | Not implemented | Not applicable

| Category | Item | Status | Evidence |
|---|---|---|---|
| Functional | Mock conversation | Verified | pytest, Vitest, Playwright |
| Functional | Realtime mock WS | Verified | test_realtime, Playwright |
| Conversation | Tier A prompt brain | Verified offline | prompt tests |
| Language | Real Gemini/Azure quality | Blocked | Gate 1 not authorized |
| Voice | Real Azure STT/TTS | Blocked | Gate 1 not authorized |
| Realtime | Interruption mock | Verified | realtime tests |
| Avatar | Performance scheduler | Partially verified | unit tests; amplitude lips only |
| Avatar | Licensed VRM | Blocked | ASSET_LICENSES quarantined |
| Memory | Explicit CRUD | Partially verified | SQLite/dev auth tests |
| Memory | Postgres RLS / OIDC | Not implemented | ADR-012/013 |
| Privacy | Dashboard API | Partially verified | `/v1/privacy/*` |
| Privacy | Polished UI | Partially verified | minimal panel if present |
| Security | Secret-free client | Verified | architecture + reviews |
| Security | Prod auth | Blocked | OIDC incomplete |
| Reliability | Paid latency | Blocked | not measured |
| Accessibility | Reduced motion / text-only | Verified | Playwright |
| Cost | Inventory | Verified empty | no cloud resources |
| Deployment | HTTPS staging | Blocked | UpCloud not authorized |
| Backup | Restore drill | Not implemented | — |
| Licence | VRM ship | Blocked | quarantined |
| Demo | Mock contingency | Verified | mock mode |

## Release blockers still open

- Real provider untested for any real-provider release claim  
- No HTTPS staging / Android trusted mic proof  
- No OIDC production auth  
- No backup restore  
- VRM licence unknowns  
- **hcnsec gateway verification decision** — flagged 2026-09-01 (Phase P3 runtime proof): `apps/api/.env.local` had `OPENAI_CODEX_BASE_URL=https://api.hcnsec.cn/v1` with a live key active, contradicting the project rule that hcnsec stays disabled until independently verified. Both `OPENAI_CODEX_*` lines are now commented out (`# HINAA-GUARD` markers) and image generation truthfully reports `IMAGE_RENDERER_UNAVAILABLE`. User action required: verify hcnsec properly (ownership, model authorization, privacy/retention, billing, security) or keep it disabled; re-enable only after verification. Also flagged but left user-configured: `CX_GATEWAY_BASE_URL` (temporary trycloudflare tunnel) and `AGENT_ROUTER_BASE_URL=https://api.mwapi.dev` (reseller-class gateway).

## Tool orchestration (Phase P3, 2026-09-01)

- Parallel tool execution verified: frontend runner dispatches `toolRequests` concurrently with per-tool status (`c1a3fa9`); Vitest 4/4 green.
- Runtime proof (mock server): registry allowlist rejects unknown tools (`404`); side-effect tools gate on `409 TOOL_CONFIRMATION_REQUIRED`; no-renderer image generation returns truthful `IMAGE_RENDERER_UNAVAILABLE` BLOCKED state.
- ComfyUI auto-detect confirmed: `health_check()` against `HINAA_COMFYUI_BASE_URL` (default `127.0.0.1:8188`) gates every job.

## Release blockers cleared

- ~~Dirty uncommitted tree (reproducibility)~~ — **CLEARED 2026-09-01** (Phase P0): in-flight voice/agent/UI work repaired and committed as `38b00fc` + `2c22129`; all gates green (backend pytest 235 passed, frontend typecheck + 186 Vitest passed, production build passed). See `HINAA_CURRENT_STATUS.md` Phase 38.

## Recommendation

**Ready for local demo only** (mock/text).  
Not ready for limited private beta or public production.
