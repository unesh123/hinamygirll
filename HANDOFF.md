# HINAA OS — Agent Coordination & Release Handoff

Branch: `antigravity/hina-recovery-v3-clean`  
Merged PR #27 (`origin/mini-code/hina-upgrade-phase1` -> `8f7d6ac`) at merge commit `0c417bd` (`apps/api/tests/test_loop_api.py` and `apps/web/src/components/ChatPanel.tsx` resolved keeping both Claude's `LoopAgentRunPanel` + Phase 3–5 loop tests and the virtualized ChatPanel v3).

## What Changed

### 1. Approval Gate Fix (`"Run has no pending approval"`)
- `apps/api/hinaa_api/agent/live_agentic_service.py`: Persist `status="awaiting_approval"` and `PendingApprovalRecord` to `AgenticRunStore` inside `_wrapped_on_event` **before** emitting `confirmation.required` over SSE, eliminating the race between UI click and disk persistence; deduplicated `confirmation.required` emission and added `is_active_agentic_run`.
- `apps/api/hinaa_api/main.py`: Updated `/v1/agent/agentic-runs/{run_id}/approve` (`/api/v1/...`) to recover interrupted `running` runs when a matching `argumentsHash` is supplied (`background=True` returns `"background": True`), clear `pending_approval` cleanly on approve/deny, and return `409 Conflict` when a run already finished/cancelled.
- `apps/web/src/features/companion/useCompanionController.ts`: Clears stale approval banners cleanly on `404`/`409` instead of leaving the user stuck on an expired modal.

### 2. Brain Providers, XKiro 25/day Image Generation & Browser Use v4
- `apps/api/hinaa_api/config.py`: Updated `xkiro_model` default (`openai/gpt-6.2-sol`), bypassed retired 404 defaults (`mistralai/mistral-large-4-0`, `mistralai/mistral-medium-3.5`), put verified HTTP 200 XKiro models first, set `coarena_model` default to free-tier `deepseek-v4-1-flash-1017` (with `gpt-6-luna` and `gemini-3-8-flash` allowed), added `xkiro_daily_image_limit=25`, and added `active_browser_use_base_url` normalizing `browserbase.com` / `cloud.browser-use.com` / `/v2` to `https://api.browser-use.com/api/v4`.
- `apps/api/hinaa_api/providers/openai_llm.py`: Added reasoning fallback extraction in `_chat_json` and clear upstream error mapping for `HTTP 402` (`PROVIDER_QUOTA_OR_TIER`) and `HTTP 403 IP_NOT_ALLOWED` (`PROVIDER_IP_NOT_ALLOWED`).
- `apps/api/hinaa_api/capabilities.py`: Exposed `cantrustai` (`deepseek/deepseek-v4.1-flash`), free-tier `coarena` (`deepseek-v4-1-flash-1017`, `gemini-3-8-flash`, `gpt-6-luna`), `xkiro` maintenance status (`degraded` on scheduled 503 models like XKiro DeepSeek maintenance), and XKiro image generation (`openai/gpt-image-2.5 · 25/day`).
- `apps/api/hinaa_api/providers/openai_image.py` & `apps/api/hinaa_api/tools/image_generate.py`: Inherited `active_xkiro_key`/`active_xkiro_base_url` when explicit `OPENAI_IMAGE_API_KEY` is omitted, enforced/persisted `.hina/xkiro_image_quota.json` (`25/day`), and surfaced `xkiro_quota` in tool results.
- `apps/api/hinaa_api/tools/browser_cloud.py`, `apps/api/hinaa_api/routers/browser_tasks_router.py`, `apps/api/tests/test_browser_use_v4.py`: Upgraded to Browser Use v4 (`/api/v4/runs`, `/api/v4/sessions/{session_id}/queue`, `allowedDomains`, yellow/red confirmation gating, early completion exit without 90s polling, and HTML stripping for 502 responses).

### 3. Template Fallback Removal, `WorkMode.tsx` & Ultra Dashboard
- `apps/api/hinaa_api/services.py` & `apps/web/src/features/chat/components/WebsiteFoundryPreview.tsx`: Disabled single-file `design_website` injection during `muse_context` co-builds and multi-file/3D/game builds; replaced `https://hinaa.local/...` display string with `sandbox://preview/...`.
- `apps/web/src/design-system/modes/WorkMode.tsx` & `apps/web/src/shell/shell.css`: Mounted `ActivityFeedV2` inside the expanded Upper Build HUD, wired `/loop <goal>` -> `LoopAgentRunPanel` (Claude Phase 2–5 SSE harness), labeled `CanTrustAI (DeepSeek)`, and tightened `.shell-bar__link` spacing so all 11 top nav routes render unclipped at `1280px`.
- External Ultra Dashboard (`C:\Users\unesh\hinaa-ultra\core\hinaa_server.py`, `ui\index.html`, `index.html`): Added brain selector (`XKiro · GPT-6.2 Sol`, `XKiro · Grok 4.7`, `XKiro · GLM 5.4`, `CanTrustAI · DeepSeek V4.1`, `Coarena · DeepSeek V4.1`, `Coarena · GPT-6 Luna`, `Gemini 3.5 Flash Lite`), `/loop <goal>` support, mobile `@media (max-width: 768px)` responsive layout, and `/` + `/sw.js` static routes on `:8765`.

## Observed Verification Output
- `pnpm --dir apps/web exec tsc --noEmit; pnpm --dir apps/web run build`: `✓ built in 4.65s` (exit 0)
- `pnpm --dir apps/web test -- --run`: `Test Files  128 passed (128)`, `Tests  849 passed | 2 todo (851)` (exit 0)
- `pytest` (15 suites: `test_browser_use_v4.py`, `test_muse_dual_brain_and_approvals.py`, `test_openai_image_provider.py`, `test_coarena_provider.py`, `test_circuit_breaker.py`, `test_website_design.py`, `test_capabilities.py`, `test_capability_honesty.py`, `test_hina_phase3_fal_and_capabilities.py`, `test_loop_tools.py`, `evals/test_loop_agent_step.py`, `test_loop_api.py`, `test_loop_events.py`, `test_loop_engine.py`, `test_intent_router.py`): `120 passed, 1 warning in 38.43s` (exit 0)
- Live Playwright (`docs/evidence/final-pass/*`): `:5173/workspace` and `:8765/` verified at `1280x800` and `390x844` with `horizontalOverflow: false`, `brokenImageCount: 0`, `clippedNavLinks: []`, `pageErrors: []`.

## Live Upstream Gateway Status Notes
- Working live (`HTTP 200`): XKiro (`openai/gpt-6.2-sol`, `x-ai/grok-4.7`, `z-ai/glm-5.4`, `nvidia/nemotron-3-ultra`, `cohere/command-a-plus`, etc. + image `openai/gpt-image-2.5`), CanTrustAI (`deepseek/deepseek-v4.1-flash`), Coarena free tier (`deepseek-v4-1-flash-1017`, `gemini-3-8-flash`, `gpt-6-luna`), Gemini (`gemini-3.5-flash-lite`).
- Upstream account/service errors observed directly from providers: XKiro `deepseek/deepseek-v4.1-flash` (`503` scheduled maintenance), XKiro `anthropic/*` & `*-astra` (`403` plan restriction), XKiro `mistralai/mistral-large-4-0` (`404`), TokenRouter (`403 IP_NOT_ALLOWED`), Claude `api.mwapi.dev` (`403 INSUFFICIENT_BALANCE`), APMIX (`0` active models), PGSGrove (`401` tier restriction).
