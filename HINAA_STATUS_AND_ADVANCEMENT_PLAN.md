# HINAA — Full Current Status & Advancement Plan
**Date:** 2026-10-08 · **Repo:** `HINAMYGIRL` monorepo (api / web / desktop / apps) · **Basis:** full read of the prior agent conversations + direct verification against the current codebase (files opened, greps run, git log inspected).

---

## 0. SESSION LOG (2026-10-08) — shipped & verified this session
- **`tools/action_guard.py` (new)** — the verify-after-every-action engine that `computer_operator.py`/`terminal_hands.py` described only in docstrings is now real, shared code: observe → act → observe → predicate → recover/retry with backoff → rollback(snapshot) → structured `ActionReceipt` + durable `RunLedger` receipt. Transient surface exceptions retry; deterministic predicates decide success — the model never gets to say "done" on belief alone. **7/7 tests pass** (`apps/api/tests/test_action_guard.py`).
- **Occurrence-nonce unpredictability (`companionExpression.ts`)** — `computeAffectiveProfile` now takes an `occurrence` seed folded into its entropy hash; `AvatarPresence` bumps a per-utterance nonce so every redelivery of the same line acts differently (asymmetric brows, smirk tilt, aperture variance all shift) while staying deterministic per occurrence for replay/tests. Closes the "she's a hash — same line, same face every time" gap on top of the existing generative affective engine. **11/11 expression tests pass** (incl. a 25-redelivery non-repetition test), AvatarPresence tests 3/3, `tsc -b` clean.
- **Test-env fix:** installed `beautifulsoup4`, `playwright`, `exa-py` into the local venv so tool-chain imports resolve; these still need pinning into `requirements-dev.txt` (P0#2 remains open until pinned).

---

## 1. VERIFIED CURRENT STATUS — what is actually built (not claimed)

### A. Companion core — DONE and confirmed in code
| Item | Evidence in repo |
|---|---|
| Text-repetition bug fixed end-to-end | `useCompanionController.ts` (`planCompleted` gating, separate `streamTimerId`/`streamRafId`), `WorkMode.tsx` (assistant-only subtitle filter), backend turn separation in `providers/agent_router.py` + `services.py` |
| Mouth moves while user is talking — fixed | `AvatarPresence.tsx` `isListening` hard-gate (visemes clamped to 0, jaw locked, listening posture), `WorkMode.tsx` `expressionText` decoupled from `partialTranscript`, `App.tsx` `liveCompanionState` |
| Hexfield-style cinematic camera | `AvatarPresence.tsx`: emotional dolly/FOV punch, ±2.5° orbit pan, 3-axis handheld float |
| Smooth walking / catwalk locomotion | Recent commits: "perfect walking kinematics, zero foot-slip stride", knee power-curve, bipedal kinematics, multi-mascot |
| Long-generation engine | `generation/orchestrator.py` (GenerationOrchestrator, finish-reason normalization, continuation) + `generation/continuation.py` (SeamGuard, structural continuation detection, consistency pass) |
| Single capabilities contract | `GET /v1/capabilities` **and** `/api/v1/capabilities` exist in `main.py` — the web/backend drift class is closed |
| Interaction modes | `prompts/response_modes.py`: `/chat` (soft, 1–3 short paragraphs, gently offers deep mode), `/reason` (first-principles engineering), `/report` (executive documentation, PDF-ready) |

### B. Advanced infrastructure — built (the "cognitive" layer)
- **`cognitive/`** — `kernel.py`, `world_model.py`, `context_compiler.py`, `consolidation.py`, `policy_engine.py`, `resilient_router.py`, `data_lake.py`
- **`brain/`** — `coordinator.py` + `specialists.py` (multi-specialist reasoning = Reasoning Brain)
- **Deterministic guardrails** — `tools/intent_gate.py`, `tools/policy.py`, `run_ledger.py`, `circuit_breaker.py`, `harness/sandbox_policy.py` (= Deterministic Brain + audit receipts)
- **`harness/`** — `motion_brain.py`, `verifier_brain.py`, `browser_environment.py`, `canonical_event_bus.py`, `agent_scheduler.py`, `telemetry_probe.py`, `compaction_worker.py`, `model_registry.py`
- **`agents/`** — `orchestrator.py`, `worker_hive.py`; **`durable/runtime.py`**; **`astra/`** — `runtime.py`, `compiler.py`, `router.py`, `registry.py`, `events.py`
- **Memory** — `memory_v2/` (`manager.py`, `partitions.py`), `continuity/` (`retriever.py`, `promotion.py`, `finalizer.py`), `persistence/memory_service.py`
- **Evaluation** — `evaluation/offline_suite.py`; **Fleet** — `fleet/device_fleet.py`; **Continuity** — `reminder_scheduler.py`

### C. Tools & integrations — built
- **Computer fabric:** `tools/terminal_hands.py`, `tools/computer_operator.py`, `tools/ui_control.py`, `integrations/remote_pc.py`, `desktop/agent_os.py`, `apps/desktop/` scaffold
- **Browser:** `tools/browser_agent.py`, `browser.py`, `browser_automation.py`, `browser_control.py`, `browser_cloud.py`, `captcha_solver.py`
- **Creation:** `tools/image_fabric.py`, `image_generate.py`, `providers/openai_image.py`, `cloud_image.py`, `freepik_suite.py`, `pdf_generate.py`, `document_generate.py`, `website_design.py`, `deep_research.py`
- **MCP/SaaS:** `tools/github_mcp_tool.py`, `integrations/github_mcp.py`, `saas_bridge.py`, `outlook_graph.py`, `desktop_bridge_auth.py`
- **Media/misc:** `youtube.py`, `email.py`, `exa_tool.py`, `gamma.py`, `social_reach.py`, `reminder.py`, `prodcamp.py`, `tinyfish.py`, `customgpt.py`
- **Image pipeline config:** Magnific (FLUX + upscaler), local ComfyUI (`HINAA_COMFYUI_BASE_URL`), xKiro pre-wired (`XKIRO_API_KEY`, base URL, allowed models) — matching the conclusion of the xKiro evaluation (LLM fallback: yes; image gen: no — Magnific/ComfyUI stay primary)
- **Voice:** ElevenLabs Aisha wired end-to-end and prioritized over Deepgram (latest commit), `deriveSpokenText` first-real-sentence fix, barge-in playback interruption

### D. Live status
- Deployed: `https://hinaa-workspace.vercel.app` (READY per prior runs; `vercel.json` points at the active Cloudflare tunnel)
- Frontend: 82 suites / 548 tests passing, `tsc --noEmit` clean (per prior agent run, 2026-10-06/07)
- Backend: 59+ pytest suites with recent passing artifact dirs under `.runtime/pytest-*-20261006`
- Git: active `feat/*` line of work; ~15 recent commits covering voice, locomotion, brain UI, responsive island OS

---

## 2. WHAT IS LEFT — gap analysis (ranked)

### P0 — Reality discipline (do first; cheap, high leverage)
1. ~~**`hinaa_perfection_blueprint.py` is still simulation.**~~ **DONE 2026-10-08:** deleted (`hinaa_perfection_blueprint.py`, `.bat`, `scripts/` duplicate). It hard-coded `"CONNECTED"` graphs and a `99.999%` target. Standing rule: **no feature is "ACTIVE" until a real integration test executes it** (write → restart → retrieve → assert). The pytest + vitest suites are the only scoreboard.
2. ~~**Fresh-env test reproducibility.**~~ **DONE 2026-10-08:** `apps/api/requirements-dev.txt` pins `beautifulsoup4`, `playwright`, `exa-py`, `tzdata` — a clean venv can run `pytest apps/api/tests` cold.

### P1 — Frontier-grade completion (the 10 items from the architecture conversations)
| # | Goal | Already exists | Missing to be "perfect" |
|---|---|---|---|
| 1 | Durable task-graph agent runtime | `agents/`, `durable/`, `harness/` | Persisted task DAG (nodes/edges/checkpoints in DB), pause/resume across restarts, budget governor (max steps/tokens/spend) enforced in `policy_engine` |
| 2 | Five-layer memory + consolidation | `memory_v2/`, `continuity/`, `cognitive/consolidation.py` | Wire consolidation to run after real conversations; contradiction resolution ("hate React" → "like React now" → latest wins); hybrid retrieval score = semantic + recency + importance + confidence |
| 3 | World model with provenance | `cognitive/world_model.py` | Real claim extraction from conversations into entity/relation/claim records with `{source, observed_at, confidence}` — no hard-coded graphs |
| 4 | Model router with utility scoring | `omega_router.py`, `harness/model_registry.py`, `cognitive/resilient_router.py` | Explicit `utility(model, task) = quality − latency − cost + fit` score; dynamic upgrades mid-turn (casual → deep when complexity crosses threshold); provider health feed from `circuit_breaker` |
| 5 | Fully duplex live voice | Live conversation hooks, barge-in, listening gate | Explicit state machine `LISTENING/THINKING/SPEAKING/INTERRUPTED/TOOL_RUNNING`; measure and gate TTFT < 300 ms on the fast path; interruption intent classification (correction vs new request vs backchannel) |
| 6 | Desktop computer fabric | `terminal_hands`, `computer_operator`, `remote_pc`, `apps/desktop` | Capability cascade L0–L6 (process discovery → UIA → DOM/CDP → adapter → CLI → vision → input fallback); **verify-after-every-action** loop using `harness/verifier_brain.py`; Windows UIA eyes |
| 7 | MCP + A2A protocols | `github_mcp_tool.py`, `saas_bridge.py` | General MCP client (any server, not just GitHub); A2A-style inter-agent messages between HINAA sub-agents (`worker_hive`) |
| 8 | First-class evaluation | `evaluation/offline_suite.py` | Regression gate in CI: benchmark before/after every change; reward vector (reasoning/tool_choice/latency/factuality/memory_precision) instead of one score |
| 9 | 24/7 cloud continuity | `reminder_scheduler.py`, `durable/runtime.py`, Vercel | Cloud work that continues when PC is off (research/docs/image jobs), reconciles when the desktop agent reconnects |
| 10 | Security hardening (2026 breach lessons) | `intent_gate`, `sandbox_policy`, `run_ledger`, `circuit_breaker` | Capability-based (not role-based) permissions; skill vetting before any third-party skill enters the registry; out-of-band kill switch that works even if the LLM is compromised |

### P2 — Product & experience
- **HINAA Control Center:** live execution stream (task events over the existing WebSocket), action timeline, desktop mirror — extend the existing `BrainOrchestrationPanel` cyberdeck HUD.
- **Report mode → artifacts:** verify `/api/v1/documents/pdf` end-to-end from a chat turn; add PPTX export.
- **Image burst provider (optional):** config already accepts any OpenAI-compatible image endpoint — add Runware/Fal.ai as a cheap high-volume tier (keep Magnific + local ComfyUI as quality tier).
- **Chat-mode discipline audit:** automated test that chat-mode replies stay 1–3 short paragraphs and never dump deep reasoning unless `/reason` or `/report` is set.

### P3 — Research intake (from the GitHub-survey conversation)
Adopt **patterns**, don't rewrite — HINAA already has equivalents for most. Selective steals:
- **LangGraph** → checkpoint/resume patterns for the task DAG (P1#1)
- **mem0 / Letta** → contradiction-resolving memory API surface (P1#2)
- **E2B** → sandbox design reference for code execution (P1#10)
- **browser-use / OpenHands** → browser observation loop and SWE task benchmarks (P1#6, P1#8)
- **LiteLLM** → gateway/guardrail/logging ideas for `omega_router` (P1#4)
- **ComfyUI agent** → local image workflow control from chat (already have ComfyUI; add workflow-planning)

---

## 3. EXECUTION ORDER (what "advance and perfect" means concretely)

**Sprint 1 (reality):** P0#1 blueprint purge + P0#2 dependency pinning + regression gate wired into CI. → Every later claim becomes trustworthy.

**Sprint 2 (brain):** P1#1 task DAG persistence → P1#2 memory consolidation live → P1#3 world-model extraction. These three turn the existing cognitive modules from scaffolding into a real persistent brain.

**Sprint 3 (senses & hands):** P1#5 voice state machine + latency gate → P1#6 desktop fabric verify-loop → P1#7 MCP generalization.

**Sprint 4 (self-improvement):** P1#4 utility router → P1#8 eval suite expansion → P1#9 cloud continuity → P1#10 security pass.

**Sprint 5 (polish):** P2 product items.

Each sprint must end with: backend pytest green, `tsc --noEmit` clean, vitest green, and a deployed Vercel build — the same bar the previous fixes met.
