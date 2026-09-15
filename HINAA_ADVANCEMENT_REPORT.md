# HINAA — Full-System Status Report & Advancement Hand-off

**Repo:** HINAA companion AI (FastAPI backend `apps/api/hinaa_api` + React/Vite web `apps/web`)
**Branch:** `feat/hinaa-ui-polish` · **Report date:** 2026-09-14
**Purpose:** Complete, evidence-backed status so another AI can make HINAA (1) generate very long, high-context answers for 2–4+ minutes without breaking, (2) behave like a deep-reasoning assistant, and (3) always finish with a short smart summary instead of echoing text blocks.

---

## 1. EXECUTIVE SUMMARY

HINAA already has the correct *long-generation architecture* on the backend:

- A shared continuation engine, `GenerationOrchestrator` (`apps/api/hinaa_api/generation/orchestrator.py`), that: streams a segment → reads a **normalized finish reason** → decides continuation via **structural signals** (`detect_continuation_need`: mid-word stop, missing terminal punctuation, open code fence, unbalanced JSON braces, unfinished Markdown table, missing planned sections) → dedups seam overlap word-by-word (`SeamGuard`/`seam_dedup`) → final `run_consistency_pass` (closes stray fences, reports duplicated headings/placeholders).
- Config knobs: `HINAA_LLM_MAX_OUTPUT_TOKENS` (default 16,384), `HINAA_LLM_MAX_CONTINUATIONS` (default 4, clamp ceiling 8), `HINAA_LLM_STREAM_CHAR_BUDGET` (default 200,000 chars), `HINAA_LLM_TIMEOUT_SECONDS` (default 300).
- A two-channel response contract: `AssistantTurnPlan.displayText` (full document, backend cap 150,000 chars) + `AssistantTurnPlan.spokenText` (concise voice summary). Server-side deterministic summarization already exists: `plan_voice_response()` + `_plain_first_sentences()` + `_spoken_summary_from_display()` in `apps/api/hinaa_api/services.py`, and `build_plan_from_text()` in `apps/api/hinaa_api/prompts/performance.py`.

**Why she currently "repeats a small line and stops":** three concrete defects, all located and evidenced below:

1. **Web client hard-caps `displayText` at 8,000 chars** (`apps/web/src/contracts/assistantTurnPlan.ts` line ~116) while the backend can emit 150,000. Any long answer blows the zod schema; the salvage path in `parseAssistantTurnPlan` re-parses with the same schema and **throws**, so the final plan event can be dropped and the UI keeps only the suppressed/partial stream. This is the single biggest "generation breaks in the middle" cause.
2. **The Claude/agent-router providers have NO continuation engine.** `apps/api/hinaa_api/providers/agent_router.py::create_live_plan` streams once and stops at the provider's token cap. `GenerationOrchestrator` is wired only in `openai_llm.py`, `groq.py`, `gemini.py`.
3. **agent-router's live JSON-extraction streamer duplicates text.** It re-extracts `displayText` from the accumulated raw JSON on every delta and un-escapes with sequential `str.replace` calls (`\"`→`"`, `\\n`→newline, etc., order-dependent). When an escape sequence is split across chunks (`\` arrives, `n` next chunk), decoding is inconsistent between calls, `emitted_length` drifts, and the same fragment is emitted twice — i.e., the observed "repeating a small line" behavior.

Secondary defects: spokenText cap mismatch (web 4,000 vs backend 8,000), `llm_stream_idle_timeout_seconds` exists in config but the providers hard-code a uniform 300s httpx timeout, orchestrators never receive `planned_sections` so the "missing requested sections" continuation trigger is dead code, and summary quality guards are not provably applied on every live path.

---

## 2. ARCHITECTURE MAP (what exists today)

### 2.1 Turn pipeline (typed REST chat)
```
services.py::create_plan (rest) / create_live_plan (live SSE)
  → pre-turn live web search grounding (5s cap, 20+ sources, services.py ~2560)
  → context routing + compiler (_route_context_for_turn / _compile_turn_context)
  → build_turn_prompt (prompts/assembly.py: safety → identity → language → personality
      → response_mode → response_depth → professional_answer → schema contract)
  → router.llm(providerMode, brainModel)  (+ _fast_casual_provider shortcut for casual chat)
  → provider.create_plan / create_live_plan
      ├── openai_llm.py  → GenerationOrchestrator (continuations, seam dedup, consistency)
      ├── groq.py        → GenerationOrchestrator
      ├── gemini.py      → GenerationOrchestrator (gemini_family finish-reason map)
      ├── agent_router.py (Claude / anthropic + openai-compatible) → ❌ NO orchestrator
      └── mock → synthetic deltas
  → _apply_response_quality_guard(plan): strip leaked XML/<think>, _remove_repeated_passages,
      plan_voice_response() → EXECUTIVE_SUMMARY / SHORT_FULL / QUESTION / COMPLETION / ERROR
  → SSE: plan event + deltas; web useCompanionController.ts consumes
```

### 2.2 Long-generation engine (correct design — keep it)
- `generation/continuation.py`: `GenerationContinuationState` (sections, segment bookkeeping, char budget), `detect_continuation_need` (never continues past `max_segments`/`char_budget`; never continues just because a token cap hit *if* text is structurally complete), `SeamGuard` (holds a 600-char prefix buffer on continuation rounds until overlap can be proven/disproven), `run_consistency_pass`.
- `generation/orchestrator.py`: `GenerationFinishReason` normalization (`OPENAI_FINISH_REASON_MAP`, `GEMINI_FINISH_REASON_MAP`, `map_finish_reason` with cross-family fallback), `GenerationProviderCapabilities` (honest capability flags — `supports_finish_reason` must reflect reality), policy: STOP+complete→done; MAX_TOKENS+unfinished→continue; CONTENT_FILTER→never blindly continue; TOOL_CALL→hand over; ERROR→preserve completed text.
- Canonical-text rule: **the user-visible stream is never rewritten mid-flight**; repairs are report-only except closing an unowned code fence at end-of-generation.

### 2.3 Summary/voice channel (the "smart summary" the user wants)
Already specified in three layers:
- Prompt: `prompts/depth.py` — `report` depth: "displayText MUST contain the comprehensive, documented report. spokenText MUST remain strictly a concise, warm 1-sentence executive summary (under 120 characters)."
- Code: `services.py::plan_voice_response()` classifies the turn and builds the voice text from **whole sentences** (`_plain_first_sentences`, limit ~200 chars for documents), never mid-thought; `_apply_response_quality_guard` forces this whenever display > 600 chars and spoken > 200, or when spoken is a verbatim echo of display (the exact "she repeats the text back" symptom).
- Live/prose path: `build_plan_from_text()` derives spoken = first 1–2 sentences, ≤160 chars, markdown stripped.

**This mechanism is right. The task is to guarantee it runs on every provider path and never gets defeated by the web-side caps.**

---

## 3. CONFIRMED DEFECTS (evidence, impact, fix)

### P0-B1 — Web `displayText` cap 8,000 vs backend 150,000 → long answers die client-side
- **File:** `apps/web/src/contracts/assistantTurnPlan.ts` — `displayText: z.string().min(1).max(8000)` (line ~116); `spokenText: z.string().min(1).max(4000)` (line ~115).
- **Backend truth:** `apps/api/hinaa_api/models.py` — `displayText` max_length **150000**, `spokenText` max_length **8000** (line ~164).
- **Failure mode:** any answer > 8k chars fails `assistantTurnPlanSchema.safeParse`. The salvage path in `parseAssistantTurnPlan` (line ~138) rebuilds fields but then calls `assistantTurnPlanSchema.parse(...)` with the same oversized string → **throws ZodError**. Depending on the event handler (`features/companion/useCompanionController.ts`, `features/providers/backendConversationProvider.ts`), the plan event is dropped and the user is left with whatever partial stream survived — matching the reported "small line then stop".
- **Fix:** raise web caps to match backend (displayText ≤ 150_000, spokenText ≤ 8_000) **and** make `parseAssistantTurnPlan` failure-tolerant: on schema failure, keep `displayText`/`spokenText` as-is (truncate only to cap) and log — never throw away a completed long answer. Add a test with a 30k-char displayText.

### P0-B2 — Claude/agent-router providers have no continuation engine
- **File:** `apps/api/hinaa_api/providers/agent_router.py` — `create_live_plan` (line ~240) streams one shot; no `GenerationOrchestrator`, no continuation factory. Grep confirms orchestrator usage only in `openai_llm.py:365`, `groq.py:197`, `gemini.py:263`.
- **Failure mode:** long documents stop dead at the model's per-call output cap (Claude/agent-router are the *reasoning* brains, i.e., the ones users pick for exactly these answers). No seam dedup either → whole-block repetition when a gateway echoes.
- **Fix:** port the exact pattern from `openai_llm.py::create_live_plan`:
  - Anthropic path: record `stop_reason` from the `message_delta` stream event into a finish-reason holder; map `max_tokens`→`MAX_TOKENS`, `end_turn`→`STOP`, `stop_sequence`→`STOP`; build `_continuation_factory(prior)` that appends the verbatim tail (last ~6,000 chars) + "CONTINUE exactly from where it stopped… resume mid-sentence" instruction; run through `GenerationOrchestrator(max_continuations, char_budget, …)` with `emit_delta`.
  - OpenAI-compatible path: same as `openai_llm.py` (`_stream_text(prompt, holder)` already yields deltas and records `finish_reason`).
  - Extend `AgentRouterAnthropicProvider`/`AgentRouterOpenAIProvider` mapping tables so `map_finish_reason` understands `end_turn`, `max_tokens` (Anthropic style).

### P0-B3 — agent-router live JSON-extraction streamer duplicates text (the "small repeated line")
- **File:** `apps/api/hinaa_api/providers/agent_router.py::create_live_plan` (~lines 262–300).
- **Bug:** on every delta it recomputes `raw_val = current_text[match.end():]`, then `clean_val = raw_val.replace('\"','"').replace('\\n','\n').replace('\\t','\t').replace('\\\\','\\')`, then emits `clean_val[emitted_length:]`. Sequential replace is **order-dependent and not idempotent over partial input**: when a chunk ends mid-escape (`\` alone, or `\u0`), decoding differs between the previous and current call, `emitted_length` (a *cleaned* length) no longer aligns with the *newly cleaned* prefix, and fragments get re-emitted — repeated lines/garbled seams. There is also no `finish_reason` capture at all on this path.
- **Fix (two options, prefer A):**
  - **A:** Replace hand-rolled extraction with the orchestrator + a proper incremental JSON-string decoder (decode escapes only on *complete* escape boundaries; track a raw index, not a cleaned length — emit only the delta between decoded lengths). Or:
  - **B:** For gateways that answer in prose anyway, drop the JSON-streaming extraction and use the openai-style prose path (stream raw deltas through the orchestrator; build the plan from text at the end via `build_plan_from_text`). The prose path already exists and is what `_custom_text_from_raw` recovers post-hoc.

### P1-B4 — Orchestrators never receive `planned_sections` → "missing requested sections" trigger is dead
- **Evidence:** all three orchestrator constructions (`openai_llm.py:365`, `groq.py:197`, `gemini.py:263`) pass only `max_continuations`, `char_budget`, `generation_id`. `detect_continuation_need(..., planned_sections=…)` exists and handles `MISSING_REQUESTED_SECTIONS`.
- **Fix:** derive planned sections from the user request (the prompt already asks for structured reports; the `report`/`professional` modes imply sections like TL;DR / Analysis / Recommendations / Next steps) and pass them. This makes multi-part answers (e.g., "write a report with X, Y, Z") continue until every requested section exists — a major perceived-intelligence win.

### P1-B5 — `llm_stream_idle_timeout_seconds` (75s default) is not wired into providers
- **Evidence:** `config.py:304` defines it; all providers create `httpx.AsyncClient(timeout=300.0)` uniformly. A reasoning model that thinks > 75s would *not* be protected here (fine), but conversely a dead stream keeps the turn hung until the full 300s.
- **Fix:** use `httpx.Timeout(connect=X, read=idle_timeout, write=X, pool=X)` per stream so stalls are detected per-read, and keep the overall turn timeout (`asyncio.timeout(llm_timeout_seconds)`) in `services.py` as the hard ceiling.

### P1-B6 — Summary guard coverage on the live path is unverified
- `_apply_response_quality_guard` (services.py ~line 425) contains the anti-echo logic (`is_verbatim_echo`, `has_forbidden_speech_structure` → `plan_voice_response`). Verify it is invoked on **every** return path of `create_plan`/`create_live_plan` including fallback providers and `build_plan_from_text` results; today the fallback/casual paths look covered but the **mock + cross-session override** (`result.value.spokenText = ev.content`, services.py ~2690) bypasses every guard and sets spoken = full content — enforce `plan_voice_response` after it.
- Also enforce: `spokenText` must never contain ```` ``` ````, `|`, `###`, or verbatim display (guard exists — keep it, add unit tests).

### P2-B7 — Config ceilings limit "keep generating"
- `config.py` clamps `llm_max_continuations` ≤ **8** and warns above 400k char budget. 8 × 32k tokens ≈ 256k tokens theoretical, but `llm_stream_char_budget` (200k chars default) caps display first.
- If the user wants "2–4 minutes of continuous high-level content": 32k tokens/call × 8 continuations is enough; the real constraint is **wall-clock timeout** (see §4) and the client caps (B1).

### P2-B8 — Depth/mode inference is regex-only
- `prompts/depth.py` + `prompts/response_modes.py` classify with keyword regexes. Long, sophisticated prompts with words like "understand me", "document", "essay" sometimes fall through to `conversational`, which loosens structure. Low risk but worth an upgrade: when `len(user_text) > 400` or an attachment/PDF is present, bias to `report`/`professional` instead of falling through.

---

## 4. THE "KEEP GENERATING 2–4 MINUTES" KNOBS (recommended .env)

```bash
# Per-call output tokens (reasoning models spend hidden tokens before first visible token)
HINAA_LLM_MAX_OUTPUT_TOKENS=32768
# Continuation rounds on top of the first segment (config clamp ceiling = 8)
HINAA_LLM_MAX_CONTINUATIONS=8
# Hard display cap in characters for one turn (web client must match, see B1)
HINAA_LLM_STREAM_CHAR_BUDGET=300000
# Whole-turn wall clock; with continuations>=6 + 32k tokens this must be >=300s (config warns otherwise)
HINAA_LLM_TIMEOUT_SECONDS=600
# Per-read stall detection once wired (B5)
HINAA_LLM_STREAM_IDLE_TIMEOUT_SECONDS=120
```
Resulting theoretical envelope: first segment + 8 continuations × 32k tokens ≈ up to ~288k tokens ≈ far beyond a 200–300k-char document; wall-clock 10 minutes. This is the "she keeps on generating without breaking" target.

If longer is desired, change two constants in `config.py` (raise the 8-clamp to 12 and the 400k warning threshold) — plus keep web caps in sync.

---

## 5. "SHE SHOULD SUMMARIZE WHAT SHE JUST GENERATED" — DESIGN CONTRACT

Already 90% implemented; make it unconditional:

1. **display channel** = the full, rich, structured document (no length pressure).
2. **spoken channel** = ONE warm sentence (≤ ~200 chars) that summarizes *the generated content itself*, built server-side from whole sentences (`_plain_first_sentences`) — never the first line echoed, never markdown, never a repeat of the user's prompt.
3. Enforcement points to guarantee:
   - After **every** provider return (primary, retry, fallback, mock, cross-session override): call `_apply_response_quality_guard(plan)` → for `len(displayText) > 600`, `plan_voice_response()` must produce `EXECUTIVE_SUMMARY` from the document body.
   - Web fallback `deriveSpokenText(plan.displayText)` (`apps/web/src/features/audio/deriveSpokenText.ts`) stays as belt-and-braces but should never be the primary source.
   - Add tests: long display → spoken contains no `#`/```` ``` ````/`|`, is < display length, ends with terminal punctuation, and is NOT a verbatim prefix echo.
4. In the prompt stack (already present — keep): `report` depth guidance mandates "spokenText MUST remain strictly a concise, warm 1-sentence executive summary"; `response_modes.py` mandates "Never repeat whole text blocks, mirror the user prompt, or regurgitate previously stated points."

---

## 6. PRIORITIZED FIX PLAN FOR THE IMPLEMENTING AGENT

**P0 (this is the bug the user is seeing):**
1. B1 — web contract caps + non-throwing `parseAssistantTurnPlan` + test with 30k displayText.
2. B3 — replace agent-router's hand-rolled displayText extraction (order-dependent unescape + `emitted_length` drift) with an escape-safe incremental decoder or the prose path.
3. B2 — add `GenerationOrchestrator` continuation to `agent_router.py` (both Anthropic and OpenAI-compatible variants), including finish-reason capture (`message_delta.stop_reason` for Anthropic).

**P1:**
4. B4 — pass `planned_sections` into all three orchestrators (derive from user text / mode).
5. B5 — wire `llm_stream_idle_timeout_seconds` as httpx per-read timeout in streaming providers.
6. B6 — audit `_apply_response_quality_guard` coverage on all return paths; fix the mock/cross-session spoken override; add summary-channel tests.

**P2:**
7. B7 — raise config clamps if needed; keep client/server budgets in a single shared constant or a `/config` endpoint the web reads at boot.
8. B8 — depth-inference upgrade for long inputs.
9. Add SSE keepalive pings during long streams so proxies/browsers don't kill idle connections.

**Invariant rules for every change (do not violate):**
- Canonical streamed text is never rewritten during streaming (display repair is renderer-only).
- Continuation decisions come from normalized finish reasons + structural detection, never "token cap hit ⇒ keep going" alone.
- Seam dedup only strips overlaps ≥ 3 words at segment boundaries.
- The consistency pass repairs only unambiguous defects (stray open fence at end of a COMPLETED generation) and reports everything else.
- `spokenText` is summary-only for long documents; it is never the document itself.

---

## 7. VERIFICATION CHECKLIST (run after fixes)

Backend (pytest, from `apps/api`):
- Existing generation/continuation tests must stay green (`tests/test_*continuation*`, orchestrator, seam dedup, consistency).
- New: orchestrator continuation test for agent_router with a fake two-segment stream and `MAX_TOKENS` finish reasons.
- New: escape-split robustness test — feed deltas that split `\"`, `\\n`, `\u0` across chunk boundaries; assert no duplicated output.
- New: summary-channel tests per §5.4.

Web (vitest, from `apps/web`):
- `contracts/assistantTurnPlan.test.ts`: add a `displayText` of 30,000 chars → `parseAssistantTurnPlan` must succeed and preserve it.
- `assistantTurnCodec.test.ts`: streaming suppression still hides fenced-JSON plan fragments; final plan replaces partial text.

Manual smoke:
- Ask HINAA for a ~5,000-word report with explicit sections → expect: continuous streaming through continuation seams with zero duplicated lines, all requested sections present, spoken reply is one warm summary sentence, no truncated UI.
- Ask the same question through every provider mode (claude, agent-router, cx-gateway, gemini, groq, openai, mock) — all paths must pass the same checks.

---

## 8. ANSWERS TO THE OWNER'S TWO DIRECT QUESTIONS

**"Why is she repeating a small line of text and stopping?"**
Because (a) the Claude/agent-router live path re-extracts `displayText` from partially-received JSON with order-dependent unescaping — when an escape sequence spans two chunks, the same fragment is emitted twice — and that path has no continuation engine, so long generations stop at the token cap; and (b) any answer over 8,000 characters fails the web client's zod contract and the salvage parser throws, so the completed long plan is dropped client-side. Both fixes are specified above (P0-B1/B2/B3).

**"She should be smart enough to give a short summary of what she generated."**
She already has the mechanism — `plan_voice_response()` builds an executive summary from whole sentences of the generated document and `spokenText` is designed to be exactly that. The work is to (1) run this guard on every provider path including mock/cross-session overrides, (2) add the missing summary-channel tests so it can never regress, and (3) stop the client caps from destroying long documents (which is what currently makes her output look like a repeated fragment instead of document + summary).
