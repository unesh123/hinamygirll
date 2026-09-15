# HINAA Companion Repair Status - 2026-09-13

## Snapshot

HINAA is in a much healthier state after the companion repair pass. The backend and frontend suites are green, the avatar picker now uses the canonical registry, assistant replies render as safe Markdown, speech/lip-sync state is routed through one playback bridge, Image Studio has stronger job/status handling, and maker/project runs are tied more tightly to canonical runtime runs.

This is not a public-launch claim. Real provider generation, real device audio/lip-sync, long-running 24/7 behavior, and production infrastructure still need live acceptance checks before calling HINAA finished.

## Verification

| Check | Result |
|---|---|
| Backend full test suite | PASS - 622 collected tests passed (0 failed) |
| Backend P0.9 intent/media grounding slice | PASS - 44 focused tests passed |
| Backend undefined-name lint (`ruff F821`) | PASS - clean |
| Backend Verification Engine suite (`test_verification_engine.py`) | PASS - 40 tests passed |
| Backend Artifact OS suite (`test_artifact_os.py`) | PASS - 18 tests passed |
| Backend RAG v2 suite (`test_rag_v2.py`) | PASS - 5 tests passed |
| Backend Memory v2 suite (`test_memory_v2.py`) | PASS - 5 tests passed |
| Backend Agent Execution v2 suite (`test_agent_execution_v2.py`) | PASS - 4 tests passed |
| Backend Durable Task hardening suite (`test_durable_tasks.py`) | PASS - 10 tests passed |
| Backend frontier conversation memory suite | PASS - 5 tests passed |
| Backend context compiler & response intelligence suites | PASS - 12 tests passed |
| Frontend full Vitest suite | PASS - 314 tests passed, 2 existing todo (56 files) |
| Frontend typecheck | PASS - via `pnpm --filter web typecheck` (`tsc -b` clean) |
| Frontend production build | PASS - Vite/PWA build completed |
| Git safety | Worktree preserved; no reset/clean/destructive Git actions used |

## Implemented In This Milestone (Priorities A-I & Phases 10-14)

- Phase 10: RAG v2 Engine with `StructuredChunker`, `BM25Index`, dense `VectorIndex`, `EntityGraphMatcher`, `HybridRetriever` with RRF, `Reranker` with MMR diversification, and `ProvenanceEngine` with sentence-level `CitationSpan`.
- Phase 11: Memory v2 Engine with 5 isolated partitions (`WORKING`, `EPISODIC`, `SEMANTIC`, `PROCEDURAL`, `PROJECT`), `MemoryManagerV2`, pointer-based supersession chains, and REST supersession endpoint.
- Phase 12: Agent Execution v2 & `DurableTaskBridge` with checkpoint hydration without step replay, deterministic step verification conditions, and dynamic steering.
- Phase 13: Verification Engine + Self-Repair with `VerifierRegistry` (pure-function glob-pattern chains), `FailureClassifier` (9 typed categories), `RepairController` (strategy-driven self-healing), and `LoopDetector` (sliding-window cycle defense).
- Phase 14: Artifact OS with universal `ArtifactRecord` and `ArtifactManifest`, hierarchical `DocumentAST` & GFM parser, multi-format exporters (Markdown, HTML, Word DOCX, PowerPoint PPTX, Excel XLSX, PDF), `ArchivePackager` with Zip-Slip path traversal defense, and `ArtifactInspector` document linting.
- Task Runtime Hardening slice: `DurableTask` now carries mutable-state `version`, worker lease identity, lease ID, fencing token, and lease expiry. `DurableTaskStep` now carries versioning, max attempts, retry-after, and deadline fields.
- Added `0011_task_runtime_hardening` migration for lease/fencing/versioning columns plus durable side-effect journal, transactional outbox, inbox dedup table, and dead-letter table.
- Added owner-scoped task APIs for claiming work, completing a step with lease/fencing validation, pause/resume, and side-effect journaling/provider-accepted updates.
- Added task runtime tests for worker claim exclusivity, stale worker write rejection, DAG cycle rejection, idempotent side-effect journaling, checkpoint schema metadata, and pause/resume.
- Checkpoints now include schema version, runtime version, and plan revision so future checkpoint migrations can be handled explicitly.
- Side-effect journal explicitly records at-least-once semantics and does not claim exactly-once behavior for external providers.
- Fully restored and verified Frontier Conversation Memory: `recent_working_context`, `resolve_reference_intent`, and `list_training_candidates` with 100% test pass rate.
- P0.9 Intent Grounding + Entity-Centric Media Search: image-search requests now compile through a structured media intent instead of echoing raw user commands or the previous conversational sentence.
- Follow-up image commands such as "FETCH ME SOME IMAGES" now resolve against the active subject/result-set context; the verified Mikasa flow resolves to `Mikasa Ackerman Attack on Titan`.
- Noisy commands such as "I NEED MIKASA IMGES HINA FETCH THEM" now produce the clean canonical query `Mikasa Ackerman Attack on Titan`.
- Named-character image search now carries canonical subject, expected entities, alternate queries, negative terms, provider profile, and result-set metadata.
- Image search results are relevance-scored, deduplicated, and filtered before the UI receives the gallery; unrelated stock/pronoun/random results are rejected for the Mikasa test case.
- Tool-result-set metadata now records canonical subject and ordered asset IDs so follow-up commands like "second one" can bind to the exact visible result set.
- Media/search responses are intentionally concise so the UI gallery carries the visual detail while the text stays short.

- Avatar model switching now uses `avatarRegistry.ts` as the source of truth for registered HINAA models.
- Avatar selection persists by stable avatar ID with migration from the old saved URL key.
- Original, Classic, Sakura Student, Casual, Kimono, and managed custom VRM assets are accepted by the picker validator.
- Temporary blob VRM previews are no longer persisted as permanent selections.
- Avatar load failure has recovery behavior so the UI can retain/fall back instead of leaving a broken blank state.
- A shared speech playback bridge now carries utterance ID, playback state, timing source, elapsed clock, viseme events, calibration offset, and reset state.
- Browser speech no longer marks HINAA as speaking before the browser `onstart` event.
- Avatar mouth animation is driven from speech playback state instead of arbitrary repeating mouth motion.
- Speech cleanup resets lips on finish, cancel, interruption, error, and unmount.
- A speech diagnostics panel shows live playback source/state/timing/viseme data for debugging.
- Chat/work/message surfaces now use a safe Markdown renderer for headings, lists, tables, links, and code blocks.
- Unsafe raw HTML and unsafe URL schemes are blocked in rendered assistant output.
- Streamed code blocks are preserved while still displaying incomplete fences safely.
- Magnific Image Studio now sends explicit user approval metadata on generate.
- Image Studio persists/restores active job watching by scoped storage key.
- Image Studio separates "stop watching" from provider cancellation.
- Image Studio shows provider state as configured/unverified/offline instead of pretending a configured key is verified availability.
- Protected generated images are fetched through the API and converted to local object URLs for display.
- Magnific/Freepik configured provider routing was tightened: Freepik-only config now uses the Freepik base/header, Magnific uses the Magnific header.
- Magnific still-image, reference, upscale, and relight paths now use task-style provider contracts and poll the matching route.
- Magnific polling no longer treats a pending preview URL as final completion.
- Project/maker run resume no longer falsely marks a resumed canonical project run as cancelled.
- Direct tool execution now creates canonical runtime runs with owner-scoped identity, idempotency keys, persisted steps/events, and timeout handling.
- Runtime events, plan/step persistence, confirmation gating, cancellation, resume, and recovery behavior have stronger backend coverage.
- Persistent conversation intelligence now stores durable entities and episodic memories for conversation continuity.
- Durable exact recent-turn context and structured rolling summary/reference hints are compiled into REST and realtime turns.
- New owner-scoped working-context and reference-resolution routes support "continue", "redo it", "use the previous one", and similar follow-up commands.
- Migrations add `conversation_entities`, `episodic_memories`, and `training_example_candidates` without resetting existing databases.
- Hina now logs offline training/evaluation candidates from stored turns with `pending_review` status and `online_weight_update=false`.
- A read-only owner-scoped `/v1/training/candidates` route exposes pending examples for future evaluator/review tooling without training live from user messages.
- PDF generation writes owner metadata for protected generated-document downloads.
- Gamma/presentation fallback returns truthful local PDF/Markdown metadata when the provider is not configured.
- Navigation/browser/file/app/clipboard/screenshot tools are confirmation-gated.
- Video generation remains blocked by policy with `VIDEO_GENERATION_FORBIDDEN`.

## Current Working Status

HINAA can run locally with the current code and tests green. The strongest verified improvements are:

- model picker compatibility for HINAA avatars,
- safer visible assistant formatting,
- more truthful speech/lip-sync state propagation,
- stronger Image Studio provider/job behavior,
- canonical runtime/tool persistence and idempotency,
- safer maker/project runtime controls,
- protected document/image artifact delivery.
- persistent conversation/entity/task reference resolution for long-running work.
- offline experience-candidate logging for future SFT/preference/evaluation datasets.
- hardened durable task execution primitives: leases, fencing, versioned checkpoints, side-effect journal, outbox/inbox tables, DLQ, pause/resume, and DAG validation.
- entity-grounded media search with relevance filtering and concise gallery responses.

## Still Left Before "Perfect"

- Real Magnific/Freepik generation must be tested with the live key and real provider quota; the code now has mocked contract tests, not paid live-generation evidence.
- P0.9 verifies intent/query/result filtering at the backend level; live browser gallery UX and paid provider generation are still separate acceptance checks.
- Real-device lip-sync still needs browser/manual acceptance with actual TTS audio and the visible VRM canvas.
- The `vendor-react-three` frontend chunk is still large and should be split further.
- The UI is safer and more truthful, but the full Jarvis-style command center polish is still an iterative design phase.
- Code generation through project files exists, but a richer review/diff workflow should be added before calling coding "fully advanced."
- Presentation generation has a safe local fallback, but real provider PPTX/Gamma acceptance remains configuration-dependent.
- 24/7 live operation still needs production infrastructure: HTTPS, secret storage, monitoring, backups, rate limits, provider quota alarms, recovery jobs, and rollback.
- Provider health should eventually include measured authentication/quota/latency probes instead of only configured/unverified state.
- Task runtime hardening is still a substrate, not a full distributed worker system: PostgreSQL `SKIP LOCKED`, real multi-process kill tests, provider status reconciliation after crash, callback inbox consumers, and operator DLQ retry UI remain future work.
- Side-effect safety is now journaled/idempotent at the HINAA layer, but true external exactly-once execution is still not claimed and must rely on provider idempotency or recovery verification.

## Acceptance Notes

- Existing user/Antigravity work was preserved.
- No destructive Git command was used.
- No live paid image provider job was intentionally submitted during this pass.
- The app should not claim unlimited ability or public-launch readiness yet.
- "Perfect" for HINAA should mean truthful, polished, stable, safe, recoverable, and advanced.
