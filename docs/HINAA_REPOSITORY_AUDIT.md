# HINAA Repository Audit

Date: 2026-08-10 · Branch: `arena/019fec56-hinamygirll` (from `main` @ `cb483ab`)
Method: static inspection + real runs (commands and observed output recorded below).

---

## 1. Repository shape

| Item | Finding | Evidence |
|---|---|---|
| Structure | Monorepo: `apps/web` (frontend) + `apps/api` (backend), `packages/` contracts, `docs/`, `infra/`, `openapi/` | repo tree |
| Workspace manager | None at root; `apps/web` is a self-contained pnpm project (`pnpm@11.7.0` declared) | `apps/web/package.json` `packageManager` |
| Frontend | React 19.2.8 + Vite 8.1.5 + TypeScript 7.0.2, Tailwind 4, three.js 0.185 + `@pixiv/three-vrm` 3.5.5, framer-motion 13, vite-plugin-pwa | `apps/web/package.json` |
| Backend | FastAPI 0.141.1 + Uvicorn 0.52, Pydantic 2.13, SQLAlchemy 2 + Alembic, httpx | `apps/api/requirements.txt` |
| Node requirement | Node 22 (CI uses `node-version: 22`); verified on v22.22.3 | `.github/workflows/web-tests.yml` |
| Python requirement | CI targets 3.14; code contained one PEP-695 file. Now runs on ≥3.11 (verified 3.11.2) after `providers/base.py` was made `Generic[T]`-compatible | this audit run |
| Package managers | pnpm (web), pip/venv (api) | lockfiles |
| Database | SQLAlchemy; default `sqlite+pysqlite:///:memory:`; pgvector/PostgreSQL is design-target only (docs), not wired | `.env.example`, `persistence/db.py` |
| Auth | Dev-auth (`HINAA_AUTH_MODE=dev`, `X-HINAA-Dev-User`) + OIDC scaffold flag; no production IdP configured | `persistence/auth.py` |
| Env files | `.env.example` (root) + `apps/api/.env.example`; real env ignored; **no `VITE_*` secrets** | `.gitignore` |
| Build | web: `pnpm build` (`tsc -b && vite build`); api: none needed | package.json |
| Tests | web: vitest (17 files) + Playwright e2e; api: pytest (155 tests) | this run |
| Deployment | `apps/web/vercel.json`, `Dockerfile` (api), UpCloud runbooks in docs, no live env configured | repo tree |
| CI | `web-tests.yml` (vitest + Playwright e2e vs mock backend) | `.github/workflows/` |
| Secret exposure | **None found.** Regex sweep (sk-, AIza, ghp_, AKIA, xi-api-key, PRIVATE KEY) over working tree and full `git log -p`: 0 hits. One leaked debug artifact `apps/api/persona_check_output.txt` (model outputs + latencies) — removed | this run |
| Large binaries | `apps/web/public/models/hinaa.vrm.bak` 19.3 MB (committed) | `ls -la` |
| VRM assets | Active slot `/models/hinaa.vrm` **missing** (gitignored `*.vrm`); only `.bak` committed → avatar pane rendered empty on fresh clones. Fixed: loader falls back to `.bak` + honest failure card. See `HINAA_VRM_AUDIT.md` | this run |
| Audio assets | none committed (`*.wav`/`*.pcm` ignored) | `.gitignore` |

## 2. Feature status matrix (verified, not assumed)

**1 — Fully implemented and live-verified in this run**
- FastAPI app: `/health/live`, `/health/ready`, `/v1/providers`, `/v1/conversations/turns:stream`, `/v1/tools/execute`, `/v1/speech/synthesis`, `/v1/privacy/*`, WS `/v1/realtime` (route exists; WS session not exercised here — no mic in sandbox)
- Mock + local provider text conversation (browser-verified end to end, screenshots in `docs/evidence/`)
- Provider status reporting with honest states (`healthy`/`degraded`/`unavailable` + userMessage)
- VRM avatar rendering, measured camera framing, relaxed idle, blink, energy lip-sync scaffold (browser-verified)
- Explicit-memory persistence layer (SQLAlchemy; 155 backend tests pass incl. memory/privacy suites)
- `web_search` tool executor (DuckDuckGo HTML) — code path real; **live network verification blocked** by sandbox egress allowlist (only github.com reachable). Returns typed error when unreachable.

**2 — Implemented but not connected (needs credentials)**
- Gemini, Groq, OpenAI, custom gateway, agent-router, CX gateway LLM adapters
- ElevenLabs TTS/STT adapters (server-side key config, paid-call gates)
- Azure Speech STT/TTS

**3 — Mocked (and now labeled in the UI)**
- Mock conversation provider (deterministic; "Mock mode" header badge)
- Local zero-credit brain ("Offline brain" badge)

**4 — Partially implemented**
- Realtime voice: WS gateway + AudioWorklet + turn-taking + barge-in code exists with unit tests; needs a mic + voice credentials for a real session
- Tool events: registry exists; no progress-event stream (results are request/response)
- Memory UI panel: frontend uses localStorage via `useMemory`; backend privacy/memory API exists but the panel is not wired to it yet

**5 — Was broken (fixed in this pass)**
- `tsc -b` failed (TS7 removed `baseUrl`) → **production build was impossible**
- 62 TypeScript errors across 22 files
- Backend could not even import: Python-2 `except A, B:` syntax in 2 files; PEP-695 generic on 3.11
- `playwright` imported unconditionally but absent from requirements → API crash on import
- `httpx.urls.URL` (nonexistent) in `web_search`
- Frontend hardcoded `http://localhost:8000` in 2 files (breaks any deployed origin) → now `/api/...` via proxy
- Default provider was `cx-gateway` (unconfigured paid gateway) → instant "Connection Issue" for fresh installs → now `auto`
- Avatar: hard-coded 180° flip showed the **back of the head** for VRM 1.0 models; fixed cameras cropped the face; inverted arm signs put hands on the face; missing-model path rendered an empty pane
- 3 stale App tests + 8 stale backend tests (old persona/coupling contracts)

**6 — Missing (not built; honestly absent from UI)**
- Email/calendar integrations (previous fake `send_email` stub **removed**)
- Presentation generation (fake `gamma` stub **removed**)
- Image generation, files/projects area, automations, audit-history UI, avatar studio, voice-provider CRUD UI

**7 — Unsafe (fixed)**
- `webbrowser.open()` on the **server** for browser/YouTube tools → replaced with validated client-directed `open_url` actions behind `requires_confirmation`
- Playwright browser automation launched `headless=False` on server → `headless=True`; module now optional and reported unavailable when absent

**8 — Blocked by credentials**: all real LLM/voice providers (keys intentionally absent).
**9 — Blocked by VRM asset**: none (asset present and profiled).
**10 — Blocked by runtime environment**: DuckDuckGo search, Playwright browser download, Google Fonts (sandbox egress allowlist); microphone (headless).

## 3. Commands actually run (all green unless noted)

```
apps/web:  pnpm install --frozen-lockfile   ✅
           pnpm typecheck                   ✅ (was ❌ 62 errors)
           pnpm lint                        ✅ 0 errors / 3 warnings
           pnpm test                        ✅ 87 passed, 1 todo
           pnpm build                       ✅ (PWA precache 1.66 MB; main chunk 1.6 MB — code-splitting recommended)
apps/api:  python3.11 -m venv + pip install ✅
           pytest                           ✅ 155 passed (was ❌ collection error)
           uvicorn hinaa_api.main:create_app --factory  ✅ health live+ready
e2e:       playwright chromium via @sparticuz/chromium  ✅ screenshots at 1920×1080 / 1440×900 / 1280×720 / 390×844 (docs/evidence/)
           repo's own `pnpm test:e2e`       ⛔ blocked (Playwright CDN unreachable in sandbox; runs in GitHub CI)
```

## 4. Dead code removed

`components/ui/`: VRMAvatar (duplicate), AvatarStage, HinaaVoiceOrb, radial-orbital-timeline, AskHinaaButton, PlasmaGlobe, TerminalPanel, WheelModelSelector, PowerWordBadges, ScrollRevealText, ShinyText, MouseCursor, BorderBeam, badge/button/card (unused shadcn stubs) · `components/lightswind/`: AiGooeyBlob, Command, NeuralLinkBackground, Drawer (unreferenced after removing App's dead drawer state) · `components/lib/utils.ts` · backend: `tools/email.py`, `tools/gamma.py` (fake executors) · `apps/api/persona_check_output.txt` (leaked debug output).

Kept (unused but tested library code that the older architecture still references): `features/avatar/*` engine modules, `features/audio/pcm|liveVad|microphoneRecorder`, `features/tools/*` registry scaffolding. These are candidates for either re-wiring or deletion in a follow-up — flagged, not silently deleted, because they carry passing unit tests documenting intended behavior.

## 5. Honesty changes

- "Mock mode" / "Offline brain" badge in the header whenever no real AI provider is active.
- Removed the fake agent-activity theater (a `setTimeout(3000)` "Searching…" step that searched nothing). Activity steps now reflect only real work; the research panel is fed by the real `web_search` tool and shows typed errors on failure.
- "Sources" action chip appears only when real sources exist.
- Tools that need missing dependencies/credentials are not registered (reported unavailable) instead of pretending.
