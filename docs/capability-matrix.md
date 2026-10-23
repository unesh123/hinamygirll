# Capability Inventory & Verification Matrix: HNA / HINA

This capability matrix represents the verified state of the HNA / HINA repository as of October 2026. Every status is backed by executable tests, source code inspection, and runtime evidence.

## Capability States Overview

- **IMPLEMENTED_AND_VERIFIED**: Code exists, contracts are enforced, and test suites pass with concrete assertions.
- **IMPLEMENTED_NOT_VERIFIED**: Code exists in the repository, but runtime verification is incomplete or relies on manual human inspection.
- **PARTIAL**: Basic mechanics or fallback paths work, but key parts of the end-to-end loop require external infrastructure or further hardening.
- **MOCK_OR_DRY_RUN**: Simulation or safe dry-run mode operational; live real-world mutation intentionally disabled or mocked.
- **UNAVAILABLE**: Feature not implemented or external capability not supported.
- **BLOCKED**: Implementation is complete or ready, but execution cannot proceed due to missing API keys or environmental constraints.

---

## Detailed Capability Matrix

### 1. Dual-Channel Response Integrity & Structured Markdown Preservation
- **State**: `IMPLEMENTED_AND_VERIFIED`
- **Entry Point / Implementation**: `apps/api/hinaa_api/services.py`, `apps/api/hinaa_api/intelligence/answer_depth.py`
- **Required Credentials & Infrastructure**: None (in-memory logic & standard Python runtime).
- **Authorization Boundary**: Per-turn session boundary.
- **Test Coverage**: 13 unit tests in `apps/api/tests/test_response_quality.py`.
- **Known Limitations**: The spoken voice channel applies conversational brevity, while canonical display text remains complete without truncation.

### 2. Server-Owned Model Registry & Auto-Priority Routing
- **State**: `IMPLEMENTED_AND_VERIFIED`
- **Entry Point / Implementation**: `apps/api/hinaa_api/harness/model_registry.py`, `apps/web/src/features/providers/utils/resolveProviderSelection.ts`
- **Required Credentials & Infrastructure**: None for registry metadata; external API keys required only for live third-party calls.
- **Authorization Boundary**: Server-side allowlist; unrecognized model IDs rejected with 422.
- **Test Coverage**: 8 tests in `test_hina_harness.py`, 20 tests in `resolveProviderSelection.test.ts`.
- **Evidence**: Passing tests verifying verified context bounds for `gemini-2.5-flash`, `gemini-2.5-pro`, `claude-3-7-sonnet-20250219`, `gpt-4o`.
- **Known Limitations**: Dynamic runtime provider discovery via remote API endpoints is cached at startup.

### 3. Progressive Audio & Teletype Sound Lifecycle Management
- **State**: `IMPLEMENTED_AND_VERIFIED`
- **Entry Point / Implementation**: `apps/web/src/design-system/modes/WorkMode.tsx` (`playStreamChunkSound`), `apps/web/src/features/audio`
- **Required Credentials & Infrastructure**: Web Audio API supported in modern browsers.
- **Authorization Boundary**: Client interaction state machine.
- **Test Coverage**: 603 passing tests in `apps/web` (`vitest run`).
- **Evidence**: Gated audio execution logic ensuring typing sound immediately terminates when `speaking` or `thinking` ceases.
- **Known Limitations**: Audio autoplay policies in Chrome/Safari require at least one user gesture prior to first sound playback.

### 4. User Authentication & Session Tenant Isolation
- **State**: `PARTIAL`
- **Entry Point / Implementation**: `apps/api/hinaa_api/auth.py`, `apps/api/hinaa_api/models.py`
- **Required Credentials & Infrastructure**: Clerk API keys (`CLERK_SECRET_KEY`, `VITE_CLERK_PUBLISHABLE_KEY`) or mock test auth.
- **Authorization Boundary**: Bearer JWT validation on all `/api/*` and `/v1/*` routes; database filter enforcement by `user_id`.
- **Test Coverage**: Unit tests across `test_auth.py`, `test_vertical_slice_e2e.py`, and API route suites.
- **Evidence**: Zero cross-user leakages under deterministic tenancy assertions in automated test harness.
- **Known Limitations**: Tested on local mock auth tickets and query boundary assertions; live OAuth token rotation requires live Clerk cloud instance.

### 5. Computer Operator & Desktop Automation
- **State**: `PARTIAL` (with `MOCK_OR_DRY_RUN` verified)
- **Entry Point / Implementation**: `apps/api/hinaa_api/tools/computer_operator.py`
- **Required Credentials & Infrastructure**: Local OS agent daemon, PyAutoGUI, OS accessibility permissions on host.
- **Authorization Boundary**: Strict sandbox allowlist (`execute_plan` with explicit `dry_run=True` enforcement; path traversal checks).
- **Test Coverage**: Unit tests in `apps/api/tests/test_computer_operator.py`.
- **Evidence**: Dry-run plans return structured execution proposals without mutating host filesystem or issuing unapproved mouse clicks.
- **Known Limitations**: Cloud-hosted instances on Render cannot interact with a user's local laptop without a securely paired local companion daemon.

### 6. Bidirectional Realtime WebRTC Live Voice
- **State**: `IMPLEMENTED_NOT_VERIFIED`
- **Entry Point / Implementation**: `apps/api/hinaa_api/realtime.py`, `apps/web/src/features/voice`
- **Required Credentials & Infrastructure**: Google Gemini Live API key, WebRTC STUN/TURN servers.
- **Authorization Boundary**: Authenticated WebSocket/WebRTC connection.
- **Test Coverage**: Protocol state machine unit tests pass; hardware acoustic live tests require connected physical microphone.
- **Evidence**: Passing protocol serialization and event transition tests.
- **Known Limitations**: Subject to network jitter; barge-in acoustic echo cancellation requires browser AEC support.

### 7. Multi-Modal Video Generation
- **State**: `UNAVAILABLE`
- **Entry Point / Implementation**: None in active production pipeline.
- **Required Credentials & Infrastructure**: Video generation APIs (e.g., Google Veo, OpenAI Sora, Runway Gen-3).
- **Authorization Boundary**: N/A
- **Test Coverage**: N/A
- **Evidence**: Codebase currently contains image generation tool hooks, but no end-to-end video synthesis engine.
- **Known Limitations**: Video generation is deferred to future architecture phases pending cost and latency feasibility.

### 8. Live Paid Provider Execution (Anthropic / OpenAI / ElevenLabs)
- **State**: `BLOCKED` (in environment where keys are unpopulated)
- **Entry Point / Implementation**: `apps/api/hinaa_api/providers`
- **Required Credentials & Infrastructure**: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`.
- **Authorization Boundary**: Managed by backend environment configurations.
- **Test Coverage**: Mock provider tests pass completely (`hinaa-mock-v1`); live calls fail gracefully with clear configuration errors.
- **Evidence**: Backend fallback engine automatically reroutes to configured accessible models.
- **Known Limitations**: High-tier models cannot be called without funded, active third-party provider accounts.
