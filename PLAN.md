# Hina Upgrade Plan — from chat persona to real autonomous agent

## Goal and users
Hina (HINAA OS, `apps/api`) already has a large harness (loop engine, agent kernel,
tools, routers) but its autonomous coding loop runs a **simulated agent step**
(`loop_router.py` sleeps and returns "Executed repair step."). The goal is for
Hina to behave like a top-tier coding agent: real model calls, real tool
execution, full traces, governed by step/cost limits and measured by an eval set.

Working = the loop engine's turns are driven by a real LLM through the server
with keys from env, its file edits are applied and verified by the hard gate,
and every turn leaves a trace a human can audit.

## Scope
In scope (next phases):
- Real LLM-backed agent step inside the loop engine (Phase 2, this run).
- Turn traces (JSONL: prompt, model, latency, tokens, actions, outputs).
- Eval set with golden cases, run and scored; live mode gated on provider keys.
Out of scope for now: new UI surfaces, multi-agent swarm changes, deploy work,
new frontend components beyond what phase 1 shipped.

## Architecture
- Python FastAPI (`apps/api/hinaa_api`), pydantic settings in `config.py`
  (key aliases: `AGENT_ROUTER_API_KEY`, `ANTHROPIC_API_KEY`/`HINAA_CLAUDE_API_KEY`,
  `OPENAI_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`).
- Loop engine (`harness/loop_engine.py`): `run_loop(agent_step, hard_gate)` —
  hard gate (verification command) is the source of truth, agent step proposes
  changes between turns.
- New `harness/agent_step.py`: resolves the first configured provider from
  settings, calls chat completions (OpenAI-compatible or Anthropic protocol),
  model replies with a JSON action plan
  (`{"thought", "actions": [{type: write_file|delete_file|run_command, ...}]}`),
  executor applies file actions **confined to the loop workspace**; command
  execution is opt-in via `HINAA_LOOP_ALLOW_COMMANDS=1`.
- Traces: `.runtime/loop_state/<task_id>_trace.jsonl`, one line per turn.
- Tests: golden eval cases with a stubbed HTTP transport (fake model replies
  only in tests) + `scripts/eval_loop_agent.py` for live scoring when a key exists.

## Risks and assumptions
- No model provider key is set in this workspace: unit evals run against a
  stubbed transport; live scoring needs one of the key aliases above (gap stated
  to the user, nothing faked in shipped code).
- Model JSON can be malformed: tolerant parser + bounded retries, hard gate
  still decides success.
- File writes are confined to the loop workspace; no shell by default.

## Phase 2: Real agent step, traces and evals (this run)
Goal: loop turns driven by a real model with auditable traces and a scored eval set.
- [x] `harness/agent_step.py`: provider resolver + LLM step + guarded action executor
- [x] JSONL trace per turn (prompt, model, latency, tokens, actions, results)
- [x] Wire `loop_router.py` to the real step (simulator removed)
- [x] Golden eval set runs and reports accuracy/latency (stub transport)
- [x] `scripts/eval_loop_agent.py` live scorer (gated on provider key)
- [x] API tests pass
Acceptance: starting a loop at `POST /api/loop/start` with a provider key set
produces real model-driven file edits, verification receipts, and a trace file;
the eval suite reports scores without a key.

## Phase 3: Streaming agent surface (done)
Goal: the rebuilt ChatPanel shows a live loop.
- [x] Event bus (`harness/loop_events.py`) + SSE endpoint `GET /api/loop/events/{task_id}`
- [x] SSE endpoint streaming turn events wired end-to-end from `POST /api/loop/start`
- [x] ChatPanel "Agent Run" mode wired to it with stop/pause
Acceptance: user watches a loop run live from the chat surface.
(Verified 2026-11-26: launched an agent run from the chat surface in a real
browser at 390px — panel streamed loop_started → turn_verified (gate PASSED) →
loop_finished, with Pause/Stop wired to `POST /api/loop/pause|stop/{task_id}`.)

## Phase 4: Tool-calling parity
Goal: Hina uses typed tools (read files, search repo, run tests) like a coding CLI agent.
- [x] Typed tool schemas (pydantic) with per-tool approval flags
- [x] Read-only tools auto-approved; side-effecting tools require confirm flag
- [x] Eval cases extended to multi-step tool use
Acceptance: eval set reports multi-step task success rate.
(Verified 2026-11-26: `tests/test_loop_tools.py` covers schemas + approval;
evals 6-8 cover inspect→write, mixed-outcome turns and list→write→verify; all
pass. Live success rate still measured by `scripts/eval_loop_agent.py` once a
model key is configured.)
