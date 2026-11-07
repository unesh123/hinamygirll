# Hinaa — Enterprise Roadmap (verified audit, 2026-11-07)

Basis: a read-only audit of `main@92df96d` (code and config, not self-reported status files).
Sizes: S ≈ hours, M ≈ 1–3 days, L ≈ a week or more. Nothing below has been run unless it says so.

## Where things stand

| Area | Reality |
|---|---|
| Backend | Feature-rich FastAPI app, but `apps/api/hinaa_api/main.py` is 7,279 lines with ~419 routes, many duplicated under `/api`, `/v1` and `/api/v1`. |
| Tests | ~2,500 pytest functions in 218 files; ~99 web unit files and ~21 Playwright specs. CI runs on PRs only. |
| Auth | Clerk gate with a `HINAA_ALLOWED_USER_IDS` allow-list. No RBAC, orgs, API keys or per-user audit trail. |
| Data | SQLite via direct `sqlite3` (~25 call sites) plus a hand-rolled migration table. Alembic is a dependency but unused. `apps/api/data/` (user PDFs, images, logs) is committed. |
| Observability | Health endpoints only. No OpenTelemetry, metrics or error tracking, although `traceparent` is advertised in CORS. |
| Deploy | Every `vercel.json` rewrite points at a random `*.trycloudflare.com` quick tunnel; Render runs on the free plan with ephemeral SQLite. |
| Web UI | React 19 / Vite 8 / Tailwind 4, but there is no router and state lives in `App.tsx` (1,645 lines). Several god-components: `AvatarPresence.tsx` 3,936 lines, `DynamicIslandCompanion.tsx` 2,885, `WorkMode.tsx` 2,133. About 3,800 hardcoded hex colors and 3,000 inline styles. Dark theme only. Thin accessibility. |
| Dead UI | `SecurityCenterPanel`, `GoalsDashboard` and `AutopilotDashboard` (Phases 14–15) are never rendered. `features/avatar/VRMAvatar.tsx` duplicates `AvatarPresence`. |
| Avatar | VRoid anime VRM (MToon shading), about 18 expressions and 5 vowel visemes driven from text. The default `hinaa.vrm` is licensed **non-commercial**. `public/models` is ~210 MB, including duplicates and a `.bak`. |
| Skills | `SKILL.md` files are not loaded at runtime. Prompts use hand-written doctrine strings (`prompts/skill_doctrine.py`), and `skills/router.py::route_prompt_tools` has no callers. `/v1/skills` exists but the UI doesn't use it. |
| Integrations | Roughly 70 registered tools, mostly real but driven by single static env tokens. GitHub = one `GITHUB_TOKEN` plus a hard-coded read-only Copilot MCP endpoint. No generic MCP client, no GitHub App or OAuth, no repo index. |
| Simulation on prod paths | `agents/hierarchy_supervisor.py` (simulated payments), `agents/hierarchy_planner.py` / `supervisor.py` (`mock_exit_code`), `autopilot/workflows.py` (simulated research), `cognitive/kernel.py` (`MODEL_EXECUTION_NOT_CONNECTED`). |

## Stage 0 — Foundation (blocks everything else)
1. Merge or close the open PR stack (#3 → #4 → #5) and close stale #2. (S)
2. Repo hygiene. (S)
   - Remove the root `.exe`, PNGs, `old_app_temp.txt`, `output_*.txt`, `scratch/`, `workspace/`, `_incoming/`, `.refact/`, `hinaa-enterprise-starter/`, stray `apps/api/test_*.py`, duplicate VRMs and `.bak` files.
   - Untrack `apps/api/data/` and extend `.gitignore`.
   - Purge personal data from git history, which needs your sign-off.
3. Point `vercel.json` at a stable API host (named Cloudflare tunnel or a real host) and use `--frozen-lockfile`. (S)
4. Gate or remove simulation code on production paths so it runs in dev only. (S–M)
5. CI. (M)
   - Run on push to `main`.
   - Add full `ruff`, `mypy`, coverage, `pip-audit`, `pnpm audit`, a secret scan (gitleaks) and a Docker build.

## Stage 1 — Enterprise backend
1. Split `main.py` into `APIRouter` modules under a single `/v1` prefix and deprecate the duplicate prefixes. (L)
2. Identity. (L)
   - Add an org/tenant model with RBAC roles (owner/admin/member/viewer) and scoped API keys.
   - Write an append-only audit log keyed by user.
   - Check every store for tenant filters.
3. Persistence: move to managed Postgres with real Alembic migrations, and move blobs to object storage (S3/R2). (M–L)
4. Observability: add OpenTelemetry traces (FastAPI, httpx, LLM calls), Prometheus `/metrics`, Sentry, and JSON logs carrying a trace ID. (M)
5. Hardening. (S + L)
   - Add per-user and per-IP rate limits and request-size limits.
   - Tighten CORS: drop the `*.vercel.app` regex and the wildcard headers.
   - Isolate tool execution in a container (nsjail/gVisor) with CPU and memory limits.

## Stage 2 — Integration hub ("connect every repo, every skill")
1. Connector registry. (M)
   - Serve `/v1/integrations` with id, auth type, required keys, configured/healthy state and tools.
   - Replace `saas_bridge` and fold in the capabilities and tools data.
2. GitHub App. (L)
   - Org-wide install and per-user OAuth, with encrypted token storage.
   - Repo picker and active-repo scoping.
   - Webhooks for push, PR and CI events.
   - Clone → chunk → embed indexing into the existing memory/RAG for code search across all repos.
3. Generic MCP client. (L)
   - stdio and streamable-HTTP transports, with persisted server configs.
   - Discover tools into `tools/registry.py`, gated by `tools/policy.py` and `action_guard`.
4. Runtime skill loader. (M)
   - Parse `SKILL.md` frontmatter and route each turn via `route_prompt_tools`.
   - Load skill bodies on demand into prompt assembly.
   - Dedupe `skills/` against `.agents/skills/`.
5. Document every third-party key in `.env.example` and fix the `APP_COUSTOMGPT_AI_API_KEY` typo. (S)

## Stage 3 — UI/UX rebuild
1. Design system. (M)
   - One token set (color, type, spacing, radius, motion) with light and dark themes, used everywhere instead of hex and inline styles.
   - Radix primitives for dialogs, menus and popovers, plus a command palette (⌘K).
   - Respect `prefers-reduced-motion` globally.
2. App shell. (L)
   - URL routing and a store (Zustand).
   - Lazy-load each mode.
   - Split the god-components: `AvatarPresence`, `DynamicIslandCompanion`, `WorkMode`, `App`.
3. Agent workspace. (L)
   - Streaming chat with tool-call cards, a live plan and run timeline, and approvals (human-in-the-loop).
   - Memory, Goals, Autopilot and Security panels. The Phase 14–15 components already exist but are never rendered.
   - An Integrations hub screen.
4. Quality gates: axe accessibility checks, Playwright visual regression and a Lighthouse budget. (M)
5. Asset delivery: serve compressed VRM/GLB files (meshopt + KTX2) from a CDN instead of 210 MB in `public/`. (M)

## Stage 4 — Avatar realism
Code cannot make the current VRoid anime model photoreal. The realistic options are:
- **A. Upgrade the anime avatar (no new cost).** (M–L)
  - Full ARKit-52/PerfectSync expression mapping.
  - Audio-driven visemes (wLipSync) instead of text timing.
  - Micro-saccades, breathing and emotion blending.
  - Better lighting, rim light and post-processing.
- **B. High-fidelity 3D human.** (L)
  - A licensed rigged GLB with ARKit-52 blendshapes (Character Creator / MetaHuman via Blender / commissioned), rendered in three.js with PBR and subsurface skin.
  - Needs you to purchase or commission the asset.
- **C. Photoreal streaming avatar.** (M)
  - Integrate a WebRTC video avatar (Simli / Tavus / HeyGen Interactive / D-ID) behind the existing `AvatarPresence` interface.
  - True human realism, but metered per minute and needs an API key.

Whichever option you pick, first replace the non-commercial `hinaa.vrm` before any public or résumé demo.

## What makes it résumé-grade
A reviewer should be able to clone the repo, run `docker compose up`, and see:
- green CI with coverage and security scans;
- a real architecture doc and OpenAPI spec;
- tenant-isolated auth, traces in Grafana/Jaeger;
- the GitHub App and MCP integrations working end to end;
- an accessible, fast UI with recorded demos.

The `HINAA_*.md` self-reported status files should be replaced by that evidence.
