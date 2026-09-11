# HINAA production implementation plan

Updated: 2026-09-05. Status: implementation in progress; public launch is not approved by these documents.

## Product outcome

A single HINAA session connects text, live speech, projects, tools, memory, and an expressive avatar. Users can work in Nepali, Hindi, English, or natural code switching. Every visible action has an actual implementation, a terminal outcome, and a recovery path. Model intelligence is provided by configured upstream models; parity with any ChatGPT product or private model is not an acceptance claim.

The existing React/Vite and FastAPI applications are the implementation targets. Preserve current work and the existing provider adapters. The separate enterprise starter is reference material, not a second production application.

## Evidence at entry

The prior audit reported 240 passing API tests and three failing spoken-text tests. Spoken-text fallback was repaired and its 19 tests passed. Conditional hooks in App were repaired. The current checkout has substantial pre-existing changes. Earlier documents and screenshots are historical evidence, not proof of current release readiness.

## Phase 0 — Reproducible baseline and planning (in progress)

- Record current compile, test, lint, build, and security results.
- Maintain this plan, the capability backlog, and release evidence.
- Identify credentials by environment-variable name only; keep values out of frontend bundles and reports.
- Acceptance: commands are reproducible and failures remain visible.

## Phase 1 — Conversation and language correctness (in progress)

- Reinstate Nepali throughout API contracts, frontend settings, prompts, speech recognition, and speech fallback.
- Support explicit Nepali/Hindi/English and mixed conversation policies without classifying every Devanagari utterance as Hindi.
- Carry conversation identity through each backend turn; prevent shared browser-session context.
- Preserve rich display answers and concise spoken answers, decimals, multilingual meaning, and code safety.
- Remove state watchdogs that silently mark unfinished work as ready.
- Acceptance: language contract and conversation identity regressions pass; interrupted and failed turns settle correctly.

## Phase 2 — Live voice and avatar experience (in progress)

- Expose language, full-body camera, captions, pause, replay, and diagnostics with accessible controls.
- Correct press-and-hold capture across pointer cancellation, touch, keyboard, and focus loss.
- Keep microphone use explicit and visibly indicated; stop tracks and stale playback on exit.
- Show avatar download/loading/failure states and preserve text/voice when WebGL is unavailable.
- Fit full-body framing to viewport width as well as height; inspect hands, feet, and lips in the running app.
- Add provider-aligned timing where supported; do not describe text-derived visemes as phoneme-perfect.
- Acceptance: desktop/mobile layout and controls pass; real microphone, speaker echo, barge-in, and each language need measured live evidence.

## Phase 3 — Unified execution kernel (pending)

- Consolidate tool metadata and execution behind server-owned schema, authorization, timeout, cancellation, and outcome validation.
- Bind owner/conversation/run identity on the server. Never trust a client-supplied owner ID.
- Add durable tool-call records, action-specific approvals, bounded runs, and idempotency for mutations.
- Normalize chat and voice events with run/turn IDs, sequence numbers, terminal states, and reconnect behavior.
- Acceptance: adversarial ownership, replay, cancellation, timeout, and duplicate-action tests pass.

## Phase 4 — Research, memory, and knowledge (pending)

- Route current-information and explicit research requests through configured search tools.
- Preserve source URLs, retrieval timestamps, citations, conflicting evidence, and provider failures.
- Feed tool observations back into bounded reasoning; distinguish retrieved facts from model inference.
- Implement permission-filtered document retrieval and user-controlled durable memory.
- Acceptance: research evaluations test source correctness and unsupported claims; memory and retrieval cannot cross users.

## Phase 5 — Desktop and integrations (pending)

- Introduce a local authenticated desktop bridge with scoped filesystem/app access and observe-after-action verification.
- Prefer app APIs, then browser DOM/accessibility, then visual interaction.
- Separate read, draft, external mutation, and destructive actions in server policy.
- Add Freepik only against verified official API contracts, with server-side credentials and configured capability reporting.
- Acceptance: task fixtures verify intended state, bounded recovery, cancellation, and action receipts. Freepik live proof waits for a valid key.

## Phase 6 — Product polish and performance (pending)

- Smooth streaming, active-message updates, scroll anchoring, accessible composition, and keyboard navigation.
- Refine Sakura design tokens, responsive layouts, purposeful animation, and reduced-motion behavior.
- Add edit/retry/regenerate/history flows backed by actual persisted conversation state.
- Measure bundle/load, frame rate, voice latency, and memory use on desktop and a real mobile device.
- Acceptance: build and UI tests pass; performance evidence reports device/network and percentile measurements.

## Phase 7 — Production infrastructure (pending)

- Enforce authenticated owner/tenant boundaries on every data and execution route.
- Production database migrations, private object storage, quotas, bounded jobs, backup/restore, and observability.
- CI includes frontend and backend checks, security scans, browser acceptance, and a production build.
- Deployment requires staging evidence, HTTPS, validated provider budgets, rollback, and asset redistribution rights.
- Acceptance: release gates in HINAA-RELEASE-EVIDENCE.md pass with no unresolved critical findings.

## External inputs

Valid model/voice/search keys and enabled account capabilities; Freepik key when available; intended production domain/hosting/account ownership; approved avatar and voice redistribution rights; real-device microphone and native-speaker evaluation. None are fabricated by implementation work.

## Execution discipline

Implement connected slices, test the actual affected boundaries, and update evidence. A backlog item is not complete because its button or document exists. Provider configuration is not proof of a successful live request. No purchase, external publication, or production deployment is implied by local implementation.
