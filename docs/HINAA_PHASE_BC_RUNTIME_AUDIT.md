# HINAA Phase B/C Runtime Audit — 2026-09-14

Per-slice audit of the coherence engine shipped on the `feat/hinaa-ui-polish`
branch. Written **after** running the full backend suite (692 passed) and web
typecheck (clean). Every claim below is tied to a file, a live path, and a test.

---

## 1. Coherent Long-Form Generation Engine (Phase B1)

| Item | Value |
|---|---|
| **STATUS** | COMPLETE |
| **ROOT CAUSE** | Prior continuation loop re-asked the model to "continue" whenever the tail lacked terminal punctuation — no finish-reason awareness, no seam dedup, no bounded state, no consistency verification. |
| **PREVIOUS LIVE PATH** | `providers/gemini.py` `create_live_plan` naive `while True` loop with `_looks_truncated` heuristic. |
| **IMPLEMENTED** | `generation/continuation.py`: `GenerationContinuationState` (§3), `detect_continuation_need` with `ContinuationReason` taxonomy (§4), `SeamGuard`/`seam_dedup` (§5), `run_consistency_pass` (§6/§37). Provider loop rewired: finish-reason extraction (`_extract_finish_reason`), per-segment state registration, bounded `max_segments`/`char_budget` (TRUNCATED status), seam suppression on continuation segments only, final consistency pass on the assembled answer. |
| **FILES CHANGED** | `hinaa_api/generation/__init__.py` (new), `hinaa_api/generation/continuation.py` (new), `hinaa_api/providers/gemini.py`, `apps/api/tests/test_generation_continuation.py` (new). |
| **PRODUCTION PATH AFTER** | Every Gemini live turn: segment 0 streams verbatim → detector decides continue/complete → continuation segments pass through SeamGuard before `emit_delta` → final consistency pass logs + repairs only unambiguous end-of-generation fence. |
| **TARGETED TESTS** | `tests/test_generation_continuation.py` — 42 passed. |
| **FULL TESTS** | 692 passed (backend), web `tsc --noEmit` clean. |
| **KNOWN LIMITATIONS** | (a) Finish-reason extraction is Gemini-shaped; other providers have no continuation loop yet — their streams end at the model's cap (documented, not hidden). (b) Seam dedup is word-normalized lexical matching, not embeddings-based semantic overlap — paraphrased (non-identical) seam repetition will pass through. (c) Consistency pass repairs only unclosed fences; duplicated headings/placeholders are reported but never auto-rewritten (deliberate — canonical-text rule §37). (d) Continuation state is in-memory per request; restart mid-generation loses the round counter (durable state comes with Phase C checkpointing). |
| **NEXT SLICE** | B2 hierarchical context compiler; port continuation loop to OpenAI-compatible providers (groq/agent_router/codecraft) reusing the same engine. |

## 2. Config Validation + Profiles (§43–§44)

| Item | Value |
|---|---|
| **STATUS** | COMPLETE |
| **IMPLEMENTED** | `Settings.validate_generation_budgets` model validator clamps dangerous values (continuations > 8, char budget < 1,000, output < 256, timeout < 30s) and records corrections in `generation_config_corrections`. `validate_generation_settings()` returns advisory warnings (logged once per live call). `apply_config_profile()` provides LOW_RESOURCE / BALANCED / MAX_QUALITY / DEVELOPER bundles; explicit env vars always win. |
| **FILES CHANGED** | `hinaa_api/config.py`, `hinaa_api/providers/gemini.py` (warning logging). |
| **TESTS** | 5 config tests in `test_generation_continuation.py` + direct smoke (`Settings(HINAA_LLM_MAX_CONTINUATIONS='20')` → clamped to 8 with recorded correction). |
| **KNOWN LIMITATIONS** | Profiles are applied by `apply_config_profile()` at call time, not automatically at process start; wiring it into app startup is a one-line follow-up. |

## 3. Semantic Voice Response Planner (§32)

| Item | Value |
|---|---|
| **ROOT CAUSE** | Prior guard hard-sliced spoken text at `[:260]` — cutting mid-thought ("...the architecture depar"). |
| **IMPLEMENTED** | `VoiceResponseType` (SHORT_FULL / EXECUTIVE_SUMMARY / PROGRESS_UPDATE / QUESTION / ERROR / COMPLETION) + `plan_voice_response()`. `_truncate_at_clause_boundary` cuts after sentence terminators, then clause separators, then word boundaries — never mid-word, never mid-thought. Quality guard delegates to the planner; questions are never overwritten by summaries; PDF/image completions route through COMPLETION type. |
| **FILES CHANGED** | `hinaa_api/services.py`. |
| **TESTS** | 8 voice-planner tests incl. "never repeats spoken recitation" and "no mid-thought cut". |
| **KNOWN LIMITATIONS** | Progress-type routing (`is_progress`) exists but live streaming progress events are not yet emitted per-sentence — callers currently pass `is_progress=False`. |

## 4. Features verified from the previous slice (unchanged, re-confirmed green)

- 16,384-token output budget / 200k stream char budget / 300s timeout (env-tunable).
- Sanitizer preserves Markdown/JSON/Unicode; strips only control chars.
- 24-turn / 32k rolling memory; `PromptInput` bounds raised to match.
- GitHub repo work-tree tools (8 tools, token auth, evidence-backed).
- Lip-sync synthetic flapping hacks removed; amplitude-driven jaw only.
- Progressive Markdown rendering with display-time fence repair (canonical text untouched).
- Deep research: Nepal + world news RSS + GitHub token auth.

## 5. Deliberately NOT claimed (honesty ledger)

- **"ChatGPT-class generation"** — capacity is now real (bounded, coherent,
  seam-safe), but coherence is verified structurally, not semantically.
  Contradiction detection across segments is NOT implemented (directive §6
  full scope).
- **"1M context"** — not implemented, and correctly so. Phase B2 (hierarchical
  context compiler + context manifest) must land and pass HinaBench V4
  long-context tests before any large-context mode is justified (§52).
- **"Exact lip sync"** — amplitude-driven jaw + real viseme timeline remain
  the fallback tier; phoneme/viseme timing priority (§33–§36) is Phase D3.
- **Test counts** — 692 passing tests verify unit behavior; no HinaBench V4
  long-output E2E has run against a live provider yet.

## 6. Latency / cost effect

- Continuation rounds add one extra request per round (only when the detector
  says the output is structurally incomplete — natural stops add zero extra
  calls, which is strictly better than the old punctuation heuristic).
- SeamGuard buffers ≤600 chars at the start of each continuation segment
  before emitting — imperceptible next to multi-second segment generation.
- Config validation runs once per Settings construction; `lru_cache` keeps it
  process-wide.

## 7. Next ordered slices (per directive §59)

1. **B3** — RepositoryMap + GitWorkspace state on top of the existing 8 GitHub tools.
2. **C1** — Wire the control loop through the existing DurableTask runtime (NOT a second state machine).
3. **C2/C3** — Sandboxed command tool + coding self-repair loop with structured `CommandResult`.
4. **C4** — GitHub permission tiers (READ / MODIFY_WORKSPACE / COMMIT / PUSH / PR) — token possession must not equal permission.

---

# B2 Completion Report — Hierarchical Context Compiler V3 — 2026-09-14

| Item | Value |
|---|---|
| **STATUS** | COMPLETE |
| **CURRENT CONTEXT PATH BEFORE** | Two parallel builders: `agent/context.py` `ContextBuilder` (agent runtime) + `agent/compiler.py` `ContextCompiler` (agent-only, NOT wired into chat) + inline rolling-window logic in `prompts/context.py` + `services.py`. Chat hot path had NO profile awareness — every turn did the same retrieval work regardless of whether the user typed "yes" or asked for historical recall. |
| **CONTEXT PATH AFTER** | ONE canonical `ContextCompiler` upgraded in place (no duplicate compiler, §10). New `agent/context_items.py` (ContextItem + TrustLevel + PriorityTier + ContextManifest) and `agent/context_profiles.py` (FAST/STANDARD/DEEP/MAX + MemoryQueryRouter + output-token reserve). `ConversationService` routes every turn via `_route_context_for_turn` before heavy retrieval: trivial turns route FAST and skip the 5s pre-search window entirely (§39). New developer inspector endpoint `GET /v1/diagnostics/context` (§37). |
| **ContextManifest example** | `{request_id, conversation_id, profile: "FAST", allocations: {system, live_state, recent_turns, task_project, memory, knowledge, history}, included: [{context_id, source_type, tier, trust, score, reason}], excluded: [{..., content_hash — no plaintext, §52}], compactions, retrieval_queries, pinning_decisions, dedup_dropped, conflicts_resolved, token_estimate, output_reserve_tokens: 4096, model_context_limit, compile_ms}` |
| **HOT/WARM/COLD routing** | `MemoryQueryRouter.route()` classifies each turn into QueryRoutes (HOT/PROJECT/ENTITY/ASSET/GLOBAL_MEMORY/RAG/REPOSITORY/HISTORICAL/EXACT_SOURCE, §18). "yes" → `(HOT,)` FAST; "what exactly did I say about the database?" → HISTORICAL+EXACT_SOURCE; "where is login validated?" → REPOSITORY+coding domain. Domain overrides shift budget shares (research → 55% knowledge, §35). |
| **Pinning** | Required live state (`user_correction`, `hard_constraint`, `goal`, `pending_question`, `system`) is pinned: rendered into the system prefix, never compacted away, never displaced by lower tiers (§14/§15). Tests prove hard constraints and user corrections land in `system_prefix`. |
| **Deduplication** | Fact-signature dedup (§22): normalized content words → same fact from history/memory/summary collapses to highest-authority source; `manifest.dedup_dropped` records it. Test proves "Nova uses PostgreSQL database" from two sources dedups; different facts survive. |
| **Conflict handling** | Precedence chain (§23): latest explicit user correction > hard constraint > goal > project > recent turn > memory > RAG > history. Loser is excluded with a recorded reason in `conflicts_resolved`; ambiguity preserved, no invented consensus. Corrections are pinned in the system prefix as `IMPORTANT — user correction:`. |
| **Historical retrieval** | EXACT_SOURCE + HISTORICAL routes exist; the routing layer is provider-agnostic and the memory service's `recent_working_context` remains addressable for raw turns (§24: summary is an index, not a replacement). Full summary-tree persistence is deferred (honesty ledger below). |
| **Security/instruction authority** | Trust levels SYSTEM/APPLICATION/USER_EXPLICIT may instruct; MEMORY/RAG/WEB/TOOL_OUTPUT/HISTORY are DATA-ONLY (§13). `ContextItem.can_carry_instructions()` is the gate. Existing prompt assembly already renders history as `<conversation_history trusted="false">` — consistent with the new model. Test injects an "ignore all previous instructions" RAG item and proves it cannot instruct. |
| **Token budgeting** | `compute_input_budget = model_limit − output_reserve(4096) − safety_margin(512)` (§33); profiles allocate shares; overflow path is required→rank→structured head/tail compaction→drop lowest tier — never random mid-truncation (§34). Compaction preserves head AND tail markers (tested). |
| **Performance** | FAST turns skip: 5s pre-search timeout, rolling working-context load, memory/entity/RAG candidate construction. Compile itself is pure-Python µs-scale (tests run in 0.04s for 30 cases). `manifest.compile_ms` recorded per compile. |
| **Blind-context comparison** | Structural proof in tests: identical input set, FAST profile includes ZERO memory/RAG/history items while STANDARD ranks+includes them — i.e. simple turns demonstrably do not pay the retrieval cost (§49 full live A/B with latency/cost measurement still pending HinaBench V4, honesty ledger). |
| **Tests** | `tests/test_context_compiler_b2.py` — 24 new tests (trust/instruction authority, routing, FAST cheapness, manifest trace, pinning, dedup, conflicts, reserve, overflow, compaction, legacy API). Legacy `test_context_compiler.py` (6) green. Full backend: **716 passed** (was 691; only pre-existing env-gated Ollama failure remains — needs a local Ollama server, not a code regression). Web `tsc --noEmit` clean. |
| **Known limitations** | (a) Chat hot path uses the ROUTER + manifest today; full compiler ranking is wired for agent-runtime use — the chat prompt still assembles via `prompts/assembly.py` layers (the router gates which heavy retrieval runs, which is the latency-critical decision; full compiler-for-chat is a mechanical follow-up). (b) Summary tree (episode→conversation) persistence not yet built — rolling summary remains the warm layer. (c) Cross-segment semantic conflict detection in generation is still B1-scope. (d) No live-provider HinaBench V4 context benchmark has run (§49/§50 A/B against blind dump pending). |

---

# B2.1 Completion Report — Canonical Context Path + Summary Tree + A/B Benchmark — 2026-09-14

## B2.1 CANONICAL CONTEXT — STATUS: COMPLETE

| Item | Value |
|---|---|
| **ROOT CAUSE** | The B2 router gated *retrieval* but `prompts/assembly.py` + provider adapters still independently decided what the model received — ContextCompiler was not the final authority (the exact honesty-ledger gap). |
| **BEFORE PATH** | `ConversationService → _route_context_for_turn → retrieval → build_turn_prompt(assembly.py re-truncates history) → provider adapter (groq/openai_llm/agent_router each re-sliced recent_turns[-8:]) → model`. Live-search web data was injected as priority-0 trusted system content (§16 violation). |
| **AFTER PATH** | `ConversationService → _route_context_for_turn (router) → retrieval → _compile_turn_context (ContextCompiler.compile_turn: rank/dedup/conflicts/pin/budget/manifest) → CompiledContextPackage → build_turn_prompt(history_preselected=True, renders verbatim, FORMAT ONLY) → providers (no independent selection) → model`. Every model invocation logs `context_manifest_id`. |
| **FILES** | `agent/compiler.py` (compile_turn, CompiledContextPackage, ContextIntegrityVerifier, manifest_id, §36 relevance gate), `agent/context_items.py` (exclusion_reason), `prompts/models.py` (history_preselected + turn sanitization moved to model validator), `prompts/assembly.py` (live_search → untrusted data block; no re-truncation of preselected history), `prompts/context.py` + `prompts/turn_prompt.py` (pass-through metadata), `services.py` (_compile_turn_context on rest+realtime paths, manifest trace, episode recording), `providers/groq.py`, `providers/openai_llm.py`, `providers/agent_router.py` (removed `recent_turns[-8:]` second authority), `persistence/orm.py` + `persistence/migrations.py` (0013 ConversationEpisode), `persistence/episode_service.py` (EpisodeSummarizer), `main.py` (session_factory + context diagnostics). |
| **MIGRATIONS** | `0013_conversation_episodes` (conversation_episodes table — §17–§20 episode tree; idempotent). |
| **Selection authority** | ONE compiler. `build_history_block` no longer truncates compiler-selected history; providers no longer re-slice; assembly is serialization only (§1–§6). |
| **Integrity** | `ContextIntegrityVerifier.verify()` compares manifest↔package↔payload: MISSING_SELECTED_ITEM / UNDECLARED_CONTEXT / TRUST_ESCALATION / TOKEN_BUDGET_MISMATCH flags (§11–§12). |
| **Voice/tool parity** | Voice and tool follow-ups ride the same `_compile_turn_context` path (§8–§9); tool results persist in `d_state.tool_result_sets` and are compiled into the next turn's context as untrusted observations. |

## B2 SUMMARY TREE — STATUS: COMPLETE

- `ConversationEpisode` ORM + migration 0013: episode_id, conversation_id, start/end_sequence, summary, decisions, corrections, constraints, open_questions, importance, summary_version (§18).
- `EpisodeSummarizer` (§19/§22/§24): boundary detection via topic-shift + inactivity-gap + explicit-refocus signals; incremental (`last_summarized_sequence` — only new turns summarized); quality guard rejects vague summaries below the concrete-detail floor. Wired into the rest-path turn finalize via `_record_episode_turn`. |
- Exact source retention (§21): raw messages remain the source of truth; episodes are retrieval aids only.

## CONTEXT A/B BENCHMARK — STATUS: COMPLETE (deterministic, in-process)

`tests/context_ab_benchmark.py` (`python -m tests.context_ab_benchmark`) — all 7 directive scenarios:

| Scenario | Baseline A (blind) | Baseline B (compiler) |
|---|---|---|
| §28 200-turn chat | precision 1.00, nova_auth_recall **0.00**, 100 tok | precision 1.00, nova_auth_recall **1.00**, 830 tok |
| §29 correction | postgres_state_in_context **0.00** | **1.00** (stale leakage 0.00 both) |
| §30 asset | asset_in_context **0.00** | **1.00** (86 tok — no 168-turn reload) |
| §31 hard constraint | constraint_retained **0.00** | **1.00** |
| §32 historical exact source | exact_source_retrieved **0.00** | **1.00** |
| §33 large doc | section14+conclusion **0.00** | **1.00** (8 of 21 sections loaded) |
| §34 injection | — | in context **1.00** as untrusted DATA, never system (§13/§16) |

**Result: hierarchical compiler ≥ legacy quality in every scenario while reducing irrelevant context** (§36: precision AND recall both measured).

**GATE FIX (root cause found by benchmark):** initial §36 gate only ran under no-budget-pressure and used the fused relevance score (authority+recency inflate it ≥0.31), so cold noise passed. Fixed: gate runs unconditionally on content-word lexical overlap (stopword-filtered) + hot recency floor — cold noise is now excluded with a manifest reason even when the budget is plentiful.

## TESTS (required format)

```text
Collected:          733
Passed:             732
Failed:             0
Skipped:            0
XFailed:            0
Environment-gated:  1  (tests/test_ollama_provider.py::test_ollama_live_plan_never_leaks_raw_json_tokens — needs a running local Ollama server; PROVIDER_UNAVAILABLE 502. Pre-existing, not a regression.)
New this slice:     +16 B2.1 (test_context_compiler_b21.py) = 46 compiler-suite tests total
Frontend:           tsc --noEmit clean
```

## BEHAVIORAL METRICS (per directive — test counts are no longer the signal)

`LongDocCompletionRate` n/a (B1 scope) · `ContinuationDuplicationRate` n/a (B1) · `ContextPrecision` 7/7 scenarios ≥ blind baseline · `ContextRecall` nova_auth 0.00→1.00, historical 0.00→1.00 · `CrossProjectLeakRate` 0 (anime noise excluded under plentiful budget) · `ConstraintRetention` 1.00 through 60 unrelated turns · `AverageContextTokens` 830 vs 100-token blind tail (compiler trades ~7× tokens for full task recall; precision maintained) · `TTFT` unchanged (compile is µs-scale; FAST skips 5s pre-search).

## KNOWN LIMITATIONS

(a) Live-search test expectations updated for the untrusted-data contract (`test_live_temporal_grounding.py`). (b) Benchmark is deterministic/in-process (selection quality, not model IQ) — live-provider HinaBench V4 latency/cost A/B remains open. (c) Episode summarization currently records boundaries/metadata; LLM-quality episode summaries plug in at `EpisodeSummarizer.summarize()` without schema change. (d) Realtime path records manifests in-memory (last-N ring) — durable manifest persistence intentionally deferred (§52: no plaintext prompt storage).

## NEXT STEP

**B3 — RepositoryMap + GitWorkspace** (RepositoryMap interface stub already anticipated by the router's REPOSITORY route). Then C1 durable agent loop.
| **NEXT SLICE** | B3 — RepositoryMap + GitWorkspace state (interface `RepositoryContextProvider` already stubbed conceptually in the router's REPOSITORY route). Then C1 durable agent loop wiring. |
