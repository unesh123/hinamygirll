# HINAA OS — Phase 5–10 Master Build Brief (for AntiGravity + ML AI Code)

> Coordination contract. Both agents work this repo; do not redo each other's work.
> Repo: `unesh123/hinamygirll` (monorepo: `apps/api` Python FastAPI, `apps/web` React/Vite).
> Working branch: `mini-code/hina-upgrade-phase1` (PR #27). Read `PLAN.md` and
> `BROWSER-AGENT-TRUTH.md` first. Do not trust summaries — read the code.

## Ground truth: what already exists (verified 2026-11-26)

| Capability | Where | State |
|---|---|---|
| Real LLM agent step (provider chain, JSON action plans) | `apps/api/hinaa_api/harness/agent_step.py` | Done, tested |
| Hard verification gate (done only when check exits 0) | `loop_engine.py::execute_hard_gate` | Done, tested |
| JSONL traces (model, latency, tokens, actions, outcomes) | `agent_step.py` | Done |
| SSE live agent-run feed, pause/stop | `routers/loop_router.py`, `apps/web/.../LoopAgentRunPanel.*` | Done, browser-verified |
| Typed tool registry, approval gating | `harness/loop_tools.py` | Done — **9 tools** |
| Research tools: `search_files`, `fetch_url`, `browser_check` | `agent_step.py` | **Done this phase** (25 tool/eval tests) |
| Tool results fed back to the model next turn | `agent_step.py::_observations` | **Done this phase** |
| Zero-LLM intent router (8 routes) | `hinaa_api/intent_router.py` | Done, 24 tests |
| Multi-step golden evals (12 cases) | `tests/evals/test_loop_agent_step.py` | Passing on stub transport |

**Hard rules for both agents**
1. Every claim of "done" requires a real check with exit 0, named in the report.
2. No simulated steps, no placeholder implementations in shipped code.
3. Tools with side effects require `confirm: true` in the action (see `loop_tools.py`).
4. File ownership — AntiGravity: `apps/web/src/design-system/modes/WorkMode.tsx`,
   `apps/web/src/features/audio/useLiveConversation.ts`, `docs/evidence/*`.
   ML AI Code: `apps/api/hinaa_api/harness/*`, `routers/loop_router.py`, tests, `PLAN.md`.
   Anything else: claim it in a commit message first.

## Phase 5 — Research & self-observation tools (THIS PHASE — done)

- `search_files` — literal text search, `file:line` matches, auto-approved.
- `fetch_url` — http(s) only, `file://` blocked at execution; fetches docs/APIs.
- `browser_check` — headless Playwright: HTTP status, title, body text, overflow-x,
  console errors, at a chosen viewport. This is the seed of "she can see her own UI".
- Observation loop: `LLMAgentStep` keeps `_observations`; the next turn's prompt
  includes `Tool results from your previous turn:` — the model can now
  inspect → reason → act across turns instead of acting blind.

## Phase 6 — Preview-in-chat (next; AntiGravity + ML AI Code)

Goal: like Claude Code / Codex — she builds a site and the user sees the live
preview inside the chat.

1. **Dev-server tool** (`run_dev_server` in `loop_tools.py`): start `pnpm dev` in a
   workspace subdir on a free port (3000–3010), health-check with `browser_check`,
   report the URL as an action outcome. Needs `HINAA_LOOP_ALLOW_COMMANDS=1`.
2. **Preview card in chat** (web): extend `LoopAgentRunPanel` — when an action
   outcome contains a `preview_url`, render an iframe card under the run feed.
   Event: `loop_events.EVENT_BUS.publish(task_id, "preview_ready", {url})`.
3. **Screenshot tool** (`screenshot_page`): Playwright PNG per viewport
   (390px + 1280px, per `.mlai/CONVENTIONS.md`), saved under
   `docs/evidence/<task_id>/`, and referenced in the trace so the *model* can be
   shown failures (multimodal pass in Phase 8).

## Phase 7 — Media references at scale

Goal: accept up to ~50 images and multiple videos (100–500 MB) as task context.

1. **Attachment ingest API**: `POST /api/loop/{task_id}/attachments` — multipart,
   streamed to disk (never full-buffer), sha256 dedupe, size caps, mime sniff.
2. **Images**: sample frames → captions via the configured vision provider;
   store a per-image `MediaInsight` (objects, text, palette, aspect).
3. **Videos**: `ffmpeg` keyframe sampling (1 fps → storyboard grid), audio track →
   transcription (Whisper-compatible endpoint when a key exists), scene-cut
   detection for structure. Only derived artifacts are stored long-term.
4. **Reference pack tool** (`list_media`, `describe_media`) so the agent loop can
   query insights without loading bytes into context.

## Phase 8 — Long context & multimodal reasoning

1. Prompt budgeter in `agent_step.py`: pack system + observations + media insights
   into the provider's context window, truncate middle-out with a summary of the
   dropped span (target: 100k+ words of source text via chunked summarization).
2. Map-reduce document understanding tool (`digest_document`) for large text dumps.
3. Vision pass: attach screenshot PNGs to provider calls that accept images so the
   model can critique its own rendered UI (closes the loop opened in Phase 6).

## Phase 9 — Self-review & autonomy

1. **Reviewer pass**: after the hard gate passes, a second model call critiques
   the diff (fresh context, same rules) and its findings become a repair turn.
2. **Approval UX**: `confirm`-gated actions surface in the web UI as
   Approve/Deny buttons on the SSE feed (wire `loop_events` → `LoopAgentRunPanel`).
3. **Continuous mode**: `run_loop` with max_turns raised + checkpointed ledger
   (already on disk) so long builds resume after restarts.

## Phase 10 — Environment & safety

1. Sandboxed workspace per task (path confinement already enforced; add
   network egress allowlist for `fetch_url`/`run_command`).
2. Provider key management: keys from env/Vault only — never in code or traces.
   Currently **no key is configured**, so the loop honestly reports
   `NO_LLM_CONFIGURED` instead of faking it. Add one key to make her live.
3. Live eval scoring: `scripts/eval_loop_agent.py` against a real provider once a
   key exists; report accuracy/latency/cost per golden case.

## Verification standard (both agents)

```
cd apps/api && python -m pytest tests/test_loop_tools.py tests/evals/test_loop_agent_step.py \
  tests/test_loop_api.py tests/test_loop_events.py tests/test_loop_engine.py \
  tests/test_intent_router.py -q -o addopts=""
cd apps/web && npx tsc --noEmit && pnpm test
```

UI changes additionally: render at 390px and 1280px in a real browser; no overflow,
clipping, overlap or contrast failures (`.mlai/CONVENTIONS.md`).
