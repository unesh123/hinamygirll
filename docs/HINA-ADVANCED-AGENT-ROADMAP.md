# HINAA — Advanced Agent Master Roadmap

**Status audit: 2026-09-14 · branch `feat/hinaa-ui-polish`**

This document is the master implementation plan for taking HINAA from
"companion with tools" to a **continuous, ChatGPT-class advanced agent**.
It combines the completed audit of this pass with the phased roadmap for the
remaining work.

---

## Part 1 — What was audited and fixed in this pass (Phase A)

### A1. Generation length — the root cause of "small blocks of text"

| Problem found | Fix shipped |
| --- | --- |
| Gemini streamed with `max_output_tokens=500` and a hard **4,000-character** cap; plan JSON capped at 1,800 tokens | Settings-driven budget: `HINAA_LLM_MAX_OUTPUT_TOKENS=16384`, `HINAA_LLM_STREAM_CHAR_BUDGET=200000` |
| Groq capped at 1,800 (chat) / 500 (stream) tokens | Same settings-driven budget |
| OpenAI/cx-gateway/agent-router capped at 8,192/4,096 | Settings-driven budget |
| Anthropic direct defaulted to 8,192 | Settings-driven default |
| **No continuation loop** — when the model stopped at its cap, the turn just ended | Gemini `create_live_plan` now auto-continues up to `HINAA_LLM_MAX_CONTINUATIONS=4` rounds when the output ends mid-sentence/mid-fence (`_looks_truncated` heuristic + seamless "resume, do not repeat" continuation prompt) |
| `llm_timeout_seconds=60` killed long generations mid-stream ("stuck in the middle") | Raised to 300s + new `HINAA_LLM_STREAM_IDLE_TIMEOUT_SECONDS=75` |
| `AssistantTurnPlan.displayText` field cap 150,000 | Unchanged (sufficient) — stream budget is now the effective ceiling at 200k chars |

**Result:** HINAA can now produce multi-thousand-word documented reports in a
single turn, streaming token-by-token for minutes, instead of stopping after
a paragraph.

### A2. The sanitizer was destroying Markdown

`_sanitize_delta` in **three providers** (Gemini, Groq, OpenAI-family) stripped
`<`, `>`, `{`, `}` from every streamed token — deleting Markdown headings,
code fences, tables, and JSON braces from user-visible text.

**Fix:** all three sanitizers now strip only ASCII/C1 control characters.
Structured output survives streaming intact.

### A3. Memory — "she forgets everything after 8 turns"

| Before | After |
| --- | --- |
| `session_turn_limit=8`, history 4,000 chars | `session_turn_limit=24`, history 32,000 chars (env-tunable) |

32k chars ≈ 8k tokens of rolling conversation history — enough to hold a full
document plus follow-up discussion in context.

### A4. Voice replies repeating the document

The quality guard already distilled spoken text, but a 300-char spoken recap
of a 5,000-char report still passed.

**Fix:** new global document guard in `_apply_response_quality_guard`:
when `displayText > 600` chars and `spokenText > 200` chars, the voice channel
is forced to a ≤180-char executive summary + "the full document is in chat".
Voice stays short/sweet; the screen keeps the full document. This is the
two-channel ChatGPT pattern enforced at the framework level, not by prompt hope.

### A5. Deep research — Nepal + world news, GitHub auth

- New `nepalnews` source: Kathmandu Post, Setopati, Onlinekhabar RSS —
  recency-ordered live Nepali headlines.
- New `worldnews` source: Google News RSS — live world coverage, any topic.
- `_search_github` now sends `GITHUB_TOKEN` when configured (higher rate
  limits, private-repo search).
- Research fan-out is now 8 parallel sources with independent timeouts.

### A6. GitHub work-tree tools (new capability — `tools/github_tools.py`)

HINAA can now **continuously work on the user's repositories**:

| Tool | Effect | Confirmation |
| --- | --- | --- |
| `github_repo_overview` | branches, issues, language, activity | no |
| `github_read_file` | read file / list directory at any ref | no |
| `github_write_file` | create/update file as a **real commit** | yes |
| `github_create_branch` | branch from any ref | yes |
| `github_list_commits` | recent commit history | no |
| `github_create_pull_request` | open PR from working branch → base | yes |
| `github_list_issues` | open/closed issues | no |
| `github_create_issue` | file an issue | yes |

Configure with `GITHUB_TOKEN` + optional `HINAA_GITHUB_DEFAULT_REPO`.
All writes are real commits with explicit messages — auditable and revertible.

### A7. Lip sync — the "air error"

Two synthetic behaviors fought the real audio pipeline:

1. **Fake jaw oscillation**: whenever jaw energy dipped <0.05 while speaking,
   a sine oscillator forced the mouth open (0.2–0.85) — the mouth flapped
   during natural pauses between words. **Removed.** Real amplitude comes from
   the Web Audio analyser (`useAudioPlayback` → `jawEnergyRef`), which is
   already frame-accurate.
2. **Unconditional viseme cycling**: whenever the viseme timeline said
   "closed" (a pause), a random syllable cycler overrode it. **Now gated**:
   it only runs when the model produced *no* viseme timeline at all.

Net effect: lips move exactly with the audio, close on consonants/pauses,
and never flap on silence. The mouth-closing-on-stop behavior (jaw → 0 when
playback ends) was already correct and is untouched.

### A8. Streaming UI — documents render as documents while generating

`ResponseMarkdown` now accepts a `streaming` prop: mid-stream, unclosed code
fences are closed at display time so the document renders as real Markdown
(headings, tables, lists) **while generating** instead of dumping raw text.
The final render is untouched. `MessageBubble` passes `streaming` during
generation.

### A9. Environment documentation

`.env.example` now documents every new knob with defaults and the reasoning
behind them.

---

## Part 2 — Gap analysis: what separates HINAA from ChatGPT-level today

| Capability | ChatGPT-class bar | HINAA now | Gap |
| --- | --- | --- | --- |
| Max single-turn output | 100k+ chars, continues for minutes | 200k char budget, continuation loop | ✅ closed in Phase A |
| Context held per conversation | Very long, with summarization | 32k chars rolling | ⚠️ Phase B |
| Live knowledge | Search + cite, current news | 8-source fan-out, RSS news | ✅ Phase A / ⚠️ depth in Phase C |
| Structured documents | Markdown + exports (PDF/DOCX) | Full artifact OS exists | ✅ already strong |
| Voice vs text channels | Short smart voice, full text | Enforced two-channel | ✅ Phase A |
| Continuous agent work | Multi-step autonomous loops, verify/retry | Agent kernel exists (plan→execute→verify→replan, 12 steps) | ⚠️ Phase C |
| Repo work | Clone/branch/commit/PR with error-solving | GitHub REST tools shipped | ⚠️ Phase C (needs executor wiring) |
| PC automation | GUI/computer-use | Browser tools exist; no OS-level control (by blueprint design) | ⚠️ Phase D (opt-in) |
| Avatar presence | Lip sync + expression | Fixed in Phase A | ✅ |
| 1M context | Managed memory hierarchy | Not yet | 🔴 Phase B/C |

---

## Part 3 — Remaining phases

### Phase B — Long-context brain (1M-class memory) — *highest impact next*

1. **Hierarchical context compile.** Replace the flat 32k rolling history with
   the compiler in `agent/compiler.py` (already exists, `max_tokens=8192`):
   - Layer 0: verbatim last N turns (always kept)
   - Layer 1: per-conversation running summary, regenerated every ~10 turns
     by a cheap model call (Gemini Flash)
   - Layer 2: durable memory facts (memory_v2 partitions already exist)
   - Layer 3: retrieval (pgvector) over full history for topical recall
2. **Streaming-safe summary.** Summaries run *after* the turn completes, in
   the background — never block the reply.
3. **Context budget settings:** `HINAA_CONTEXT_COMPILE_TOKENS` (target 100k+,
   model-dependent), with per-provider ceilings (Gemini 1M, Claude 200k,
   GPT 128k) selected by the router.
4. **Test:** 100-turn conversation with a document pasted at turn 5 must still
   answer questions about it at turn 90.

### Phase C — Continuous agent loop ("keep working until I stop")

The pieces exist separately; wire them into one loop:

1. **Goal loop** (`agent/kernel.py` has max_iterations=8 → raise to
   configurable, default 25):
   - User gives a goal ("fix the failing tests in repo X and open a PR").
   - Kernel plans → executes → verifies (verifier_registry has
     `builtin.web_search` and artifact verifiers) → replans on failure.
2. **Continuous mode UI:** a "Run" session surface showing the live work tree
   of steps (like this agent's todo list), with a Stop button. Stream every
   step event over the existing SSE channel (`agent.run.*` events already
   defined in `agent/events.py`).
3. **Repo executor wiring:** connect `AgentRuntime.executor` to the GitHub
   tools + a sandboxed local worktree (`local_workspace_dir` config already
   exists) so the loop can: read code → propose edits → run tests (bash) →
   commit → PR. Guardrail: every write-tool call requires the existing
   `requires_confirmation` approval or explicit autonomy grant.
4. **Bash tool (sandboxed):** a `shell_run` tool restricted to
   `local_workspace_dir` with an allowlist (`pytest`, `npm test`, `tsc`,
   `git status`…), timeout, and output size caps — enough for self-error-
   fixing loops without OS exposure.
5. **Stop conditions:** user stop button, step budget, wall-clock budget,
   cost budget (`creative/budget_manager.py` pattern), and a "no-progress
   detector" (same verifier twice → ask the user).

### Phase D — PC automation (opt-in, owner-gated)

The blueprint explicitly forbids autonomous device control in the MVP; make it
an explicit opt-in tier:

1. **Scope ladder:** web-only (today) → sandboxed workspace shell (Phase C)
   → OS automation (new).
2. **OS tier:** PyAutoGUI/OS-level keyboard+mouse behind a per-action
   confirmation UI, plus an allowlist of apps; screen-state vision loop
   (screenshot → multimodal model → action) for "computer use".
3. **Safety:** kill switch, audit log (sanitizer already redacts secrets),
   never runs on lock screen, per-app permissions persisted in memory_v2.

### Phase E — Model routing & cost

1. **Depth-based routing** (fast-path exists): conversational → Gemini Flash;
   documents/research/repo-work → the strongest configured reasoning model;
   summarize/distill → cheap model. `providers/agent_router.py` already
   supports this — surface it as per-request `responseMode` (exists) plus
   automatic depth inference hardening (`prompts/depth.py`).
2. **Next-token prediction quality:** enable provider-native "thinking"
   budgets for reasoning models (thinking_config on Gemini, reasoning_effort
   on OpenAI-compatible) — configurable, default high for professional/report
   modes, off for chat.
3. **Cost caps:** reuse `creative/budget_manager.py` for LLM spend per
   day/session; expose in `/usage`.

### Phase F — Image generation polish (audit follow-ups)

Current flow (Freepik/Magnific/local ComfyUI) is strong. Remaining polish:

1. **Relevance scoring:** after image_search, rank results against the actual
   prompt (embedding cosine) and drop below-threshold hits instead of showing
   6 mediocre ones.
2. **Style memory:** remember user's accepted styles in memory_v2
   ("anime, soft shading") and bias prompt compilation.
3. **Progress:** stream `image.progress` events (percent) — the SSE plumbing
   exists (`tool.progress`).

### Phase G — Evaluation harness (prove it works)

1. Extend `evaluation/offline_suite.py`:
   - Length suite: "write a 2000-word report on X" → assert ≥1500 words,
     assert Markdown structure, assert spokenText ≤ 200 chars.
   - Continuity suite: 50-turn chat → assert early-document recall.
   - Research suite: assert ≥2 live sources and citation links in report mode.
   - Repo suite: mock GitHub API → assert read→edit→commit→PR sequence.
2. Wire the suite into CI (tests/eval_10k exists as a starting point).

---

## Part 4 — How the "continuous generation + thinking work tree" works now

```text
User turn
  └─ stream_turn() (SSE)
       ├─ planning.started
       ├─ research events (live, per-source)   ← deep_research fan-out
       ├─ text.delta × N                        ← token-by-token, minutes-long
       │    (provider → continuation loop when truncated → more deltas)
       ├─ tool.* events (approval → execution → result)
       ├─ plan (final AssistantTurnPlan)
       │    ├─ displayText: full 200k-capable document → rendered live
       │    └─ spokenText: ≤180-char executive summary → TTS
       └─ run.completed
```

Voice plays the summary immediately; the document keeps streaming to the
screen; the quality guard guarantees the voice never recites the document;
the continuation loop guarantees the document never dies at a token cap.

---

## Part 5 — Quick-start config for "maximum HINAA"

```env
HINAA_LLM_MAX_OUTPUT_TOKENS=16384
HINAA_LLM_STREAM_CHAR_BUDGET=200000
HINAA_LLM_MAX_CONTINUATIONS=4
HINAA_LLM_TIMEOUT_SECONDS=300
HINAA_SESSION_HISTORY_CHAR_LIMIT=32000
GITHUB_TOKEN=ghp_xxx
HINAA_GITHUB_DEFAULT_REPO=youruser/yourrepo
```

Nothing else is required — every new behavior is on by default with these
defaults, and every cap is tunable per environment.
