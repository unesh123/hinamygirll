# 78 — HINAA Advancement Plan: Deep Thinking, Documents, and Autonomy

Status: **Phases A+B shipped (this branch) · Phases C–D planned with acceptance gates**
Date: 2026-09-11 · Owner: Arena AI continuation sessions
Supersedes the vibe-plan received from the previous agent session; every item
below is anchored to real files and verifiable commands.

---

## 0. Why this document exists

The product ask, in one line: *HINAA should answer like a senior engineer
writing a document, speak like a smart assistant (never re-reading the screen
aloud), render images that match the exact subject, move her lips while she
talks, and take commands the way power users type them (`/`).*

Everything in **Phase A** is implemented and test-verified in this tree.
Phases B–D are the sequenced path to the "autonomous workstation" tier, with
honest effort estimates and hard acceptance gates — no 100%-guarantee
language; anything not verifiable from this repo is marked as dependent on
external keys/accounts.

---

## Phase A — Accuracy & polish (SHIPPED this branch)

| ID | Deliverable | Where | Evidence |
|----|-------------|-------|----------|
| A1 | **Real Magnific FLUX API contract** (was a guessed sync endpoint — the root cause of "image generation not generating"). `api.magnific.com`, `x-magnific-api-key`, async task pattern: POST → `task_id` → poll `GET {path}/{task_id}` until `COMPLETED`/`FAILED`. `flux-dev` (quality), `flux-2-turbo` (fast), `flux-kontext-pro` for reference-guided (`input_image`), `/v1/ai/image-upscaler` creative upscale (base64 input, prompt-reuse trick, per-style `optimized_for` profiles). Negative prompts folded into the prompt (vendor has no negative field). Seeds clamped to the vendor's 1..4,294,967,295 window. | `apps/api/hinaa_api/providers/magnific.py`, `hinaa_api/tools/image_generate.py`, `hinaa_api/config.py` | Contract transcribed from docs.magnific.com OpenAPI (flux-dev, flux-kontext-pro, image-upscaler pages). py_compile + interface kept stable for `image_generate` batch/upscale/fallback flow. |
| A2 | **Image pipeline self-diagnostic** — "not working" now says *why*: `GET /v1/image-studio/status` reports `{renderer, magnificConfigured, comfyAvailable, setup[]}`; the studio shows a green/amber/red strip with the exact `.env.local` lines to add. | `hinaa_api/main.py`, `components/ui/MagnificImageStudio.tsx` | Studio test updated to assert zero poll calls on a failed start. |
| A3 | **"Exact image" relevance** — search queries are cleaned of command noise before hitting the vendor (`fetch me some images of X in HD` → `X`), and reference-image selection scores every candidate's title/alt/filename against the subject tokens instead of trusting popularity-rank #1 (the "I asked for Mikasa, got a bridge" bug). | `hinaa_api/tools/browser.py::clean_image_query`, `hinaa_api/tools/image_generate.py::reference_from_query_result` | 8/8 cleaner cases + relevance-assertion probes executed against extracted source. |
| A4 | **Slash commands that actually work** — `/` opens the power-up palette (bare `/` lists, `/res` filters, selection inserts `/research `, completed prefix no longer hijacks Enter). ↑↓/Enter/Esc navigation verified; empty filter closes the palette so Enter returns to "send". Backend deterministic router turns `/research X`, `/image X`, `/generate …` into exact tool requests (style/ultra/count parsed from the subject line), while "can you /research" phrasing stays blocked. | `components/ui/PremiumComposer.tsx`, `PowerUpMentions.tsx(+test)`, `hinaa_api/services.py::_inject_deterministic_tool_intents` | 3 new vitest cases, 9-case regex table, live injection harness run on this tree. |
| A5 | **Heavy, document-grade answers** — response modes now *enforce structure*: `professional`/`research`/`technical`/`academic` carry explicit section/table/citation/checklist requirements ("length must match the problem"), and `/report` or `/doc` forces professional mode deterministically. Research answers consume deep-research findings instead of guessing. | `hinaa_api/prompts/response_modes.py` (+ `infer_response_mode` slash awareness) | Prompt-layer only; behavioral ceiling is the 8,000-char `displayText` budget in `models.py`. |
| A6 | **Smart voice, never an echo** — beyond the existing channel prompt, the quality guard now *deterministically distils*: when a model dumps a report into `spokenText` anyway (or echoes `displayText`), the voice line is rebuilt from the first plain sentences of the document + "full breakdown in chat". Long answers can no longer be read aloud verbatim. | `hinaa_api/services.py::_apply_response_quality_guard`, `_plain_first_sentences` | Harness: 900-char dump → <320-char distilled voice; short spoken line untouched; verbatim echo → complement line. |
| A7 | **Lips that move** — viseme amplitude previously multiplied by analyser energy which the browser-speech path never produces (audio never enters our graph) → ~0.16 weights ≈ frozen face. Speaking now has a hard 0.48 floor and audio energy only *modulates* it. Plus a **jaw-bone fallback**: the smoothed mouth weights physically rotate `Jaw` every frame, so auto-rigged VRMs with broken `aa` blendshapes still articulate. | `components/ui/AvatarPresence.tsx` (Model frame loop) | Typecheck + suite green; visual confirmation requires a browser session (manual gate below). |
| A8 | **Real PDF documents** — server-side renderer producing branded, paginated, multi-page PDFs from the *same markdown* the chat shows: section hierarchy, fpdf2 table API, shaded code blocks, blockquotes, numbered lists, link URLs preserved as `(url)`, page footers. Unicode-safe (embeds Nirmala/DejaVu when present, latin-1 sanitizes otherwise — never a crash). Endpoints: `POST /v1/documents/pdf` (any answer/dossier) and `?format=pdf` on project artifact export. Frontend: PDF action on long answers and on research cards (fixes "PDF incomplete / can't download"). | `hinaa_api/documents/pdf.py`, `hinaa_api/main.py`, `features/documents/exportPdf.ts`, `MessageBubble.tsx`, `GenericResultRenderer.tsx` | Renderer probed end-to-end: unicode font path, multi-page long document, fallback-without-fonts path, filename slugs. `fpdf2>=2.8.3` added to requirements. |

**Phase A manual gate (needs your machine, keys, and a browser — this is the
honest limit of sandbox verification):**
1. Add `MAGNIFIC_API_KEY=…` to `apps/api/.env.local` (see `.env.example`), restart the API.
2. Open the studio → strip must read "Magnific FLUX online".
3. Chat: `/image Mikasa Ackerman on the wall at sunset, anime style` → approve → job polls → image lands (upscaler runs on ultra only).
4. `/research transformer architecture` → approve → dossier card with per-source tree → "Download PDF" saves a multi-page branded document.
5. Ask anything deep ("give me a full report on X") → structured multi-section answer; **voice speaks one short line, not the report**.
6. Talk mode: lips visibly move on both cloud TTS and the browser-voice fallback.

---

## Phase B — Genuine reasoning stream (SHIPPED this branch)

The model's live reasoning now flows to the UI the moment it is produced —
without ever touching the answer, memory, or the voice channel.

| Piece | Implementation | Evidence |
|-------|----------------|----------|
| Provider extraction | `openai_llm._stream_text` yields `("content"|"reasoning", delta)` and captures `delta.reasoning_content`/`reasoning` (DeepSeek-R1, vLLM, Kimi, custom gateways). `agent_router` OpenAI wrapper passes tuples through; the **Anthropic** override parses `thinking`/`thinking_delta` events in every SDK shape (normalized or raw `content_block_delta`) — no new request params, so an unsupported gateway can't break. `groq` captures `delta.reasoning` (plus fixes an empty-`choices` IndexError that could kill a live turn). `gemini` walks `parts[].thought == True` via `getattr` guards, SDK-shape-drift safe. | py_compile + tuple-typed seams; `emit_thought=None` keeps every old call-site working (mock/local paths untouched). |
| Wire protocol | `services.create_live_plan(..., emit_thought)` threads the sink; `stream_turn` runs one queue with two channels and emits `thought.delta` frames interleaved with `text.delta` — additive SSE/NDJSON, old clients ignore it. Thoughts never enter `emitted`, the remainder-sync, the plan, history, or TTS. The "reasoning_content is intentionally never spoken" guarantee is preserved and now annotated. | Extraction harness executing the real `stream_turn` source: sequence `thinking → thought.delta → text.delta → thought.delta → … → plan`, remainder sync intact, thoughtless-provider untouched event list, mid-stream failure propagation — all asserted. |
| Frontend | `BackendConversationProvider` parses `thought.delta` (new test asserts stream order); `useCompanionController` groups deltas into **thought lines** at sentence boundaries (180-char monologue breaker for uncooperative models), runs a live thinking clock frozen at first text delta, keeps ≤40 lines, and clears on next turn — display-only, never persisted, exactly per the handoff spec's turn-end rule. `TranscriptView` → `MessageBubble` → `ThinkingWeave` now renders the latest thought with a rise animation, a duration readout, and a "watch the weave (N)" expandable numbered chain. | 4 new vitest cases (153/153 total), typecheck + build clean, oxlint zero on touched files; auto-scroll tracks thought growth. |
| Deliberately deferred | Persisting a `reasoning_summary` into turn metadata (the handoff spec's suggestion): requires a schema migration for marginal value — display-only is strictly safer than storing chain-of-thought in SQLite. Revisit only if history playback of thinking is ever requested. | — |

**Manual gate:** with a thinking-capable brain configured (agent-router/DeepSeek/Gemini-flash-thinking), send a non-trivial question: the gyre bubble should show real reasoning lines appearing under the spinner; opening "watch the weave" shows the chain; TTS still speaks only the short summary; refreshing the page shows zero trace of thoughts in chat history (by design).

## Phase C — Coding tools (sandboxed, approval-first) — v1 SHIPPED this branch

The spec document from the previous session asked for `code_workspace.py`,
`code_patch`, `terminal_runner`. Non-negotiable design constraints for HINAA
(a *companion* product, not a CI box):

1. **Workspace jail**: `hinaa_api/tools/code_workspace.py` — all paths resolved with `Path.resolve().is_relative_to(WORKSPACE_ROOT)` (the same technique `/v1/generated-images` already uses for traversal defense). Read/grep/symbol-map only; default `max_depth`/byte caps; binary detection returns metadata, not content.
2. **Patches are proposals**: `code_patch` returns a unified diff + hash of the exact target region; applying requires the existing tool-approval UI (`requires_confirmation=True`), and every successful patch writes a shadow backup under `data/patches/{id}.orig` so revert is one tool call.
3. **Terminal**: `terminal_runner.py` with argv-level parsing (`shlex`), deny-list *and* allow-list tiers (git/test/lint auto-allowed; anything writing outside the workspace or networking needs approval), `asyncio.wait_for` timeout, streamed `stdout.delta` SSE events into the existing WorkTree renderer.
4. **Self-heal loop** (the "run pytest, feed the traceback back" fantasy) is explicitly **deferred**: unattended edit-run-retry loops need sandbox isolation to be safe; v1 = HINAA proposes, human approves each execution round. Revisit when Phase D adds an OS-jail option (Windows Job Objects / bwrap).
5. **Gate**: path-traversal test matrix, deny-list fuzz test, approval-flow integration test; docs: new `adr/` entry.

Effort: 3–4 sessions. Risk: MEDIUM (security surface — hence the ordering after B).

**Phase C v2 status (SHIPPED this branch):** `hinaa_api/tools/terminal_runner.py`
registers `terminal_run` behind four walls — human approval of the exact
argv, shell-free execution (operators outside quotes are refused outright),
an escalation guard (`python -c`, shells, destructive binaries refused by
name), and a scrubbed child environment (no API key ever reaches a child —
asserted by test). Working directory is the same HINAA_CODE_ROOT jail; the
project's own `.venv` is prepended to PATH so `python -m pytest` means the
project's tools. Output tails at 64 KB, timeouts kill the tree and report
`timedOut`, nonzero exits return as *data* (the model can read failures and
self-correct) — and the auto-repair loop still needs a human per round.
`/run <command>` routes straight to the approval card; the chat renders a
terminal card (exit chip, ms, tailed marker, stderr block).
**Tests: 12 terminal + 16 code-workspace, all green in-sandbox.**

**Phase D partial:** micro-motion pack shipped — chest breath swell (scale
channel, so it can never fight the pose lock) and a rare idle brow flicker
through the expression manager, both runtime-probed per model. Remaining:
`.vrma` walk/gesture clips, packaged PDF font for Devanagari, live-mode voice
parity, staging checklist refresh.

**Phase C v1 status (shipped now):** `hinaa_api/tools/code_workspace.py`
registers `code_explore` (tree / find_files / grep / view_symbol),
`code_read` (line-window, numbered), `code_patch` (exact-match, fail-closed on
ambiguous/missing targets, backup-outside-repo, unified diff back to the UI)
and `code_write` (create-or-explicit-overwrite). Jail = `HINAA_CODE_ROOT`
(default `~/.hinaa/code-workspace`): absolute paths, `..` traversal, symlink
escapes and home/drive roots are refused; `.env*`, key material, credential
files and `.git` internals are **invisible to reads/greps** as well as refused
for writes. Explore/read are read-only and auto-runnable; patch/write are
`requires_confirmation=True` through the existing approval card. `/explore`
slash command and `@explore` / `@patch` palette entries route in; the chat UI
renders typed result cards (grep hits, numbered windows, +/- coloured diffs,
backup trail). `tests/test_code_workspace.py` — **16 tests, all green**
(traversal, symlink escape, secret blindness, ambiguity fail-closed, backup
location, overwrite guard, grep/binary/symbol behaviour, regex errors).
Terminal execution + the auto-repair loop remain deferred (unchanged rationale
above); the `stdout.delta` streaming widget will ship with them.


## Phase D — Presence & launch polish

1. **Avatar motion pack**: idle weight-shift + gesture clips via `@pixiv/three-vrm-animation` (the `.vrma` asset pipeline already exists in `public/animations`); "walking" only if an actual clip ships — procedural locomotion on humanoid rigs looks broken, and we won't ship that.
2. **Voice**: live-mode parity for the A6 distiller (gemini-live/azure realtime currently speak what the model says — apply the same concision contract at the TTS gate), barge-in ducking tests.
3. **PDF**: package a real Unicode TTF into the repo (`assets/fonts/`) so Devanagari renders everywhere deterministically; add an "Export answer" menu entry for *all* assistant messages (A8 currently gates at >700 chars to keep bubbles calm).
4. **Launch hardening**: the docker/compose + staging runbook already in docs 35–39 remain the source of truth; add the new env vars (MAGNIFIC, YOUCOM) to the staging checklist and the `pnpm check:mobile` + `playwright` suites to CI if they aren't wired yet.

Effort: 2–3 sessions. Risk: LOW–MEDIUM.

---

## Verification playbook (run after any phase)

```
# frontend
cd apps/web && pnpm typecheck && pnpm test && pnpm build

# backend (needs Python ≥3.12; fpdf2/httpx/etc.)
cd apps/api && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

Current tree at Phase A close: **149/149 frontend vitest**, tsc + build clean,
every backend file compiles, and the new logic paths (slash router, voice
distiller, query cleaner, reference scoring, PDF renderer incl. the
no-unicode-font fallback) were executed and asserted against the real source
via extraction harnesses. The backend pytest suite itself has not been run
here (sandbox lacks Python 3.12) — run it before merging, as always.

## Explicitly rejected items from the incoming spec

- "Use Gamma AI for PDFs" — a presentation SaaS; our PDFs are documents. Rejected as a dependency; the fpdf2 renderer (A8) replaces it.
- "100% everything perfect" — replaced with the gates above.
- Fast (512²) image mode suppression — kept `fast` as *flux-2-turbo at 768²*; permanently suppressing a cheaper tier would silently raise every user's API bill.
- Unsupervised auto-patch loops — see Phase C.4.
