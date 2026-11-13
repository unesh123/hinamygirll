# HINAA implementation handoff and phased acceptance plan

Date: November 13, 2026 (Asia/Katmandu)
Audience: Antigravity and subsequent engineering agents.
Purpose: finish and prove the existing product in bounded milestones. This is a plan, not a statement that every capability below exists or works.

## 1. Current release stage

**Local integration and reliability validation; not yet production-certified.** GitHub remote access is now demonstrated. Several components have meaningful implementation and unit coverage, but full user journeys, restart recovery, desktop task execution, real audio performance and staging operations still need evidence.

Repository at inspection: HEAD `81bae813dfb97291e39ca6bcaf809801da73918c`. The working tree contains important uncommitted repairs and concurrent documentation changes. HEAD alone is not the current implementation.

### Independently observed

| Area | Evidence | Limit |
|---|---|---|
| Frontend | `http://127.0.0.1:5173/` returned 200 again during this handoff | Does not establish usable login, layout or every interaction |
| Backend | `/health/live` returned 200 again | Does not establish dependency readiness or tool success |
| Frontend proxy | `/api/v1/providers` returned 200 in the repair pass | Not proof all upstream models respond |
| GitHub | PR #19 is open, draft, not merged; head `hina/feat/gate02-activation`, SHA `1722ef885b84c3206e0f4086c44bac5966d99a07`, base `main` | Proves a real remote PR exists, not that Hina autonomously executed every preceding step |
| Database | Earlier same-day read-only connection to PostgreSQL 16.16; 19 migration rows | Full backup/restore and production database use not independently repeated |
| Desktop bridge | Earlier repair pass: paired health 200/ready; unpaired 401; live enumeration returned 35 windows | No complete app-control task verified |
| Tests before repair | 812 frontend tests passed, 2 todo; 25 targeted backend tests passed | Not a fresh complete backend regression |
| Tests after repair | 19 focused backend tests and 41 focused frontend tests passed; TypeScript and Vite production build passed | GitHub success/failure responses mocked in these tests; large-bundle warning remains |

PR receipt: https://github.com/unesh123/hinamygirll/pull/19

### Claims that must remain qualified

- **“Zero amnesia”: unproven.** Persistence is not reliable recall. Measure exact recall, semantic retrieval, corrections, deletion and user isolation.
- **“Ultra-low latency”: unproven end to end.** Some UI defaults were fabricated; these are removed in the pending repair. The earlier 1113 ms audio measurement was described inconsistently as full download and first audio.
- **“Complete autonomous engineering”: partial.** A live PR and local unit tests do not prove request-to-PR execution through Hina.
- **“10 specialists”: implementation inventory, not proof of useful concurrent execution.** Require distinct actual tool/model traces and a verified combined output.
- **“Production observability”: plumbing exists/reported; operational readiness still needs alert, outage and recovery drills.**
- **“Browser refused connection because HTTPS”: possible explanation, not established diagnosis.** Inspect exact URL, listener/process, logs and actual error before assigning cause.
- **“50 tables”: reported by Antigravity; this review independently checked migration count, not all table counts.**

Yesterday's provider checks found text from Gemini, XKiro and Experiential. Several other lanes returned authentication, billing, rate-limit or upstream failures. These are historical samples, not current access guarantees or verified identities of gateway-advertised branded models.

## 2. Preserve the pending repairs first

Read `git status`, `git diff`, applicable repository instructions and these reports before editing:

- `docs/CURRENT-STATUS-REVIEW-2026-11-13.md`
- `docs/EXECUTION-REPAIR-2026-11-13.md`
- `docs/PROVIDER-VERIFICATION-2026-11-12.md`
- `PHASE_07_EXTERNAL_GATE_ACTIVATION.md` and its copy in `docs/`

Pending source changes:

1. `apps/api/hinaa_api/repository/github_flow.py`: literal task-only commits; async PR creation with explicit repo/base, remote SHA check, actual draft POST and readback; fake PR completion rejected.
2. `apps/api/hinaa_api/repository/workspace.py`: NUL-delimited UTF-8 status parsing and independent path scoping.
3. `apps/api/hinaa_api/tools/github_tools.py`: registered PR tool creates a draft and verifies its response through GET.
4. `apps/api/tests/test_governed_github_flow.py` and new `test_github_pr_verification.py`: scope preservation and PR failure regressions.
5. `WorkMode.tsx`, `AdobeMotionTimeline.tsx`, `ShowroomMode.tsx`: remove invented latency/speedup defaults.

Never reset whole files, discard unrelated changes or overwrite simultaneous Antigravity work. The governed helper is now async and must be awaited; inspect callers before integration. Do not accidentally treat the existence of this helper as proof it is wired into Hina's task orchestrator. A real PR now exists separately, but the repaired helper has not itself been demonstrated against live writes.

## 3. Execution rules for every phase

- One bounded milestone per change set: implementation, meaningful tests, real acceptance evidence, status update and scoped rollback.
- Classify each capability as **verified live**, **verified locally**, **implemented/unverified**, **blocked**, or **missing**. Identify mocks and synthetic data explicitly.
- Keep the existing routing and tool authorization authoritative on the backend. Do not let model text or frontend state grant permissions.
- Do not silently change providers when a user pins a model. Distinguish requested from actual provider/model and record failures without exposing credentials.
- Never report task completion from prose, a successful HTTP status alone, a generated filename or a tool registration. Validate the actual outcome.
- Preserve task cancellation; make external side effects idempotent where possible. After ambiguous remote writes, inspect remote state rather than blindly retrying.
- Do not print secrets, widen access, expose desktop control publicly, deploy or merge merely to make a test green. Use existing authorization and obtain any missing publication approval only after preparing a concrete result.
- Do not add broad memory systems, provider collections or orchestration frameworks to avoid fixing broken execution.

## 4. Phase plan

Phase numbers below continue the existing Phase 07 history. Old completion claims must be reconciled, not copied into new green checklists.

### Phase 08 — Consolidate baseline and truthful status (P0)

**Work:** preserve pending repairs; remove stale status contradictions; run complete backend/frontend suites and production build; inventory skip reasons, mocks, runtime processes, active database and model configuration. Ensure telemetry says unavailable when unmeasured.

**Acceptance:** reproducible commands and raw result summaries tied to commit plus dirty diff; no unexplained failures; all skipped integration gates named. Verify scoped commits preserve unrelated staged/unstaged work, filenames with spaces/Unicode, additions, deletions and renames. Verify API errors never become completed cards.

**Deliverable:** current capability matrix, baseline test receipt and reviewed repair diff. A failing relevant test blocks progression for that feature.

### Phase 09 — Complete one genuine autonomous coding workflow (P0)

**Work:** wire Hina's request/tool orchestration to isolated workspace edits, real test execution, evidence capture, scoped commits and GitHub operations. Inspect existing PR #19 without merging or recreating it. Verify origin/repository identity and expected commit before remote mutation. Keep test mocks out of runtime success paths.

**Acceptance:** issue a small feature request through Hina's actual UI/API; produce an isolated patch; run tests; exercise one failing-test repair; commit only allowed files; push an authorized task branch; create/read back a real draft PR; show its URL and SHA in Hina. Test denied permission, branch mismatch, API 403, timeout after POST, existing PR and cancellation. A dummy SHA or arbitrary “tests passed” string must not substitute for trusted execution receipts.

**Deliverable:** reproducible request-to-PR trace, patch, test output and live remote receipt. Distinguish token/account access from end-to-end agent execution.

### Phase 10 — Desktop, browser and terminal reliability (P0)

**Work:** keep bridge supervised and paired; inspect task permissions, application targeting, path scope and cancellation. Diagnose WSL/Linux availability and document the actual distro/shell. Verify tools execute on the intended machine. Retain owner boundaries and emergency stop.

**Acceptance:** Hina opens an authorized editor, creates a file in a scratch workspace, verifies saved contents and stops on command. Run one controlled browser form task on a local fixture with observed results. Run one bounded WSL/Linux command, capture exit code/output, cancel a long process, recover from a bridge disconnect. Denied actions must produce explicit failures. Do not claim complete PC control from window enumeration.

**Deliverable:** three real task receipts: desktop, browser and terminal. No credential entry, unrelated file modification or public bridge exposure in acceptance tests.

### Phase 11 — Durable execution and recovery (P0)

**Work:** identify the authoritative task store/state machine, checkpoints, leases, retry limits and side-effect receipts. Consolidate existing implementations rather than adding another scheduler.

**Acceptance:** terminate an actual worker process mid-task; restart; resume from durable state without duplicating a file publish, email or PR. Exercise concurrent workers, stale leases, cancellation during recovery, timeout and database unavailability. Verify the active application database, not only a test database. Perform backup/restore into an isolated database with content checks.

**Deliverable:** crash/restart timeline, persistence evidence, restored-data comparison and bounded retry policy.

### Phase 12 — Voice, reasoning and provider performance (P1)

**Work:** instrument speech onset/end, partial/final transcript, dispatch, first meaningful text, first audio bytes and actual playback. Stream text and speech concurrently; bound queues; cancel stale audio; adapt turn-ending to pauses. Audit response truncation, repetition and context budgets. Rank usable models using measured evidence without inventing advertised capabilities.

**Acceptance:** at least 30 representative turns with English/Nepali speech, pauses, background noise and interruption; report p50/p95 latency and errors. Initial engineering targets, not promises: partial transcript visible within 500 ms when supported, interruption stops playback within 250 ms, and first audible response p50 under 2 seconds/p95 under 4 seconds on a declared network/provider setup. If missed, publish measurements and bottlenecks. Compare reasoning correctness on a fixed task set; speed cannot mask lower accuracy.

**Deliverable:** timestamped trace, audio acceptance notes, provider availability matrix and measured before/after results. No claim of zero latency.

### Phase 13 — Responsive UI and avatar performance (P1)

**Work:** profile render cost, React updates, GPU frame time, VRM loading, texture memory and animation ownership. Repair missing/occluded hands and walking poses based on actual skeleton/mesh inspection. Blend gestures, gaze, blinking and visemes without competing animation writers. Add adaptive quality and reduced motion.

**Acceptance:** inspect desktop widths 1280/1440/1920 and mobile widths 360/390/768; no obstructed composer, selector/modal overflow or unusable keyboard interactions. Measure idle/chat/speech/walk for ten minutes on declared hardware. Proposed targets: desktop 60 FPS and constrained mobile 30 FPS with quality fallback; report measured frame-time percentiles and memory growth. Check lip/audio alignment using actual playback. Do not equate passing jsdom tests with visual or FPS verification.

**Deliverable:** screenshots, performance captures, device matrix and visual defect closure list. Humanlike presentation remains a design goal, not a claim Hina is a real person.

### Phase 14 — Memory and useful specialist coordination (P1)

**Work:** validate existing exact archives, semantic recall, corrections, provenance, privacy and context assembly. Test actual specialist execution only for tasks that benefit; keep simple conversation fast.

**Acceptance:** fixed retrieval set covering exact facts, paraphrases, conflicting updates, deletion, restart and cross-user denial. Report accuracy, misses and latency. A multi-agent task must show distinct executions, dependencies, budgets, failure handling and an independently validated final artifact; no simulated activity labels.

**Deliverable:** memory evaluation results and one justified, traced specialist workflow. Avoid “zero amnesia” guarantees.

### Phase 15 — Documents, images and connected services (P1/P2)

**Work:** finish existing artifact lifecycle before adding integrations: request contract → authorized worker → file → format validation → registration → download → completed UI. Connect reference-image workflows with explicit limitations. Inventory provider keys by names/status only. For school/work Outlook, use the appropriate Microsoft tenant consent flow and minimal required scopes; distinguish draft creation, reading and sending authorization. Apply the same explicit capability/consent model to social services and MCP servers.

**Acceptance:** real PDF and DOCX download/open; test worker failure, missing/invalid output and failed downloads. Confirm images decode and reference conditioning is actually applied. Each connector gets one read and one separately authorized write test, plus revoked-token and permission-denied tests. Unsupported social networks stay unavailable rather than advertised as working.

**Deliverable:** artifact receipts and connector matrix listing account type, required permission, configured state, tested action and blocker. No blanket “every social media” claim.

### Phase 16 — Motion Studio flagship (P2)

**Work:** distinguish extraction, analysis, procedural motion graphics, generative video, editing and export. Build a deterministic scene/timeline representation with typography, layers, easing, camera, audio beats and reusable components. Treat After Effects-like quality as a target; do not claim native editable After Effects export unless implemented and tested.

**Acceptance:** licensed 15-second audio/reference task → analysis → editable timeline → preview → rendered video → inspection → one correction pass. Validate codec, dimensions, duration, audio sync, fonts and output download. Compare beat alignment, transitions, typography, motion and consistency to a declared rubric. Record render duration, memory and provider cost. Generating an MP4 alone fails acceptance.

**Deliverable:** rendered clip, editable source/timeline, inspection notes and cost/performance receipt. Native generative video remains separately classified until an actual provider workflow passes.

### Phase 17 — Authenticated staging and operations (P0 for release)

**Work:** before any public ingress, verify actual authentication enforcement, user isolation, tool authorization, rate/resource limits, secret handling and dependency readiness. Identify the implemented Cloudflare Access validation path if used; an asserted header name in a report is not evidence. Determine frontend rewrite targets, backend hosting, WebSocket support, storage and worker lifetimes separately.

**Acceptance:** with publication authorization, test deployed frontend → backend → authenticated task, plus unauthenticated and wrong-user denial, expired sessions, origin restrictions, stream reconnects and backend outage. Desktop bridge remains private. Configure alerts and prove they fire. Perform an isolated rollback/restore drill and a real 24-hour monitored run with failures, resource use and recovery recorded.

**Deliverable:** deployment manifest, public reachability receipts, security tests, operational runbook and soak report. Local health 200 is not a deployment receipt.

### Phase 18 — Private beta and release decision (P2)

**Work:** recruit a small authorized test group; publish only supported capabilities; establish support, usage limits, data retention and cost controls. Gather native-speaker feedback where relevant.

**Acceptance:** fixed task set across coding, documents, voice and optional media; measure completion rate, human interventions, latency, cost, failures and retention. Close critical data-loss/security defects. Define numeric release thresholds before collecting results, then publish pass/fail without changing the rubric afterward.

**Deliverable:** beta evidence, known limitations, support/rollback owner and explicit go/no-go decision. Public launch is a separate authorized action.

## 5. Order and dependencies

Start **08 → 09 → 10 → 11**. Then validate voice and UI (**12–13**), memory/specialists (**14**), artifacts/connectors (**15**) and the creative flagship (**16**). Staging design and security review may begin early, but public activation in **17** waits for the core reliability gates and authorization. Beta **18** follows staging and the minimum advertised feature set; optional creative features can remain excluded until ready.

Do not schedule by impressive phase names or claim completion percentages. Estimate each bounded work package only after inspecting implementation and test failures. External access, hardware, quota and consent blockers must be named precisely.

## 6. Required end-of-milestone handoff format

1. Baseline SHA, initial dirty files and exact changed files/hunks.
2. Defect and resulting user-visible behavior.
3. Commands, exit codes, pass/fail/skip counts and warnings.
4. Mocked versus live checks and evidence locations.
5. Actual output: artifact hash/download, PR URL/SHA, task trace or performance capture.
6. Remaining failures and external blockers; no generalized perfection claim.
7. Rollback limited to milestone changes, preserving unrelated work.
8. The next bounded milestone and its acceptance criteria.

## 7. Immediate instruction to Antigravity

Read this handoff and inspect the current dirty diff. Preserve Codex's execution repairs and your concurrent report edits. Complete Phase 08, then prove Phase 09 through Hina's actual task path. PR #19 already exists: verify and reuse its evidence; do not claim it proves the new helper or full autonomy. Do not deploy, merge, introduce another framework or start a broad UI redesign to bypass these gates. Return concrete implementation and verification results, not another architecture-only report.
