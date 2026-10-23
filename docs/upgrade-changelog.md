# Upgrade Changelog & Engineering Audit Trail

This changelog records all engineering modifications, architectural refactors, and test additions implemented during the comprehensive stabilization and response integrity upgrade of HNA / HINA.

---

## [Unreleased] - 2026-10-16

### 1. Response Integrity & Truncation Elimination
- **Affected Files**:
  - `apps/api/hinaa_api/services.py`
  - `apps/api/hinaa_api/intelligence/answer_depth.py`
  - `apps/api/tests/test_response_quality.py`
  - `apps/api/tests/test_response_lifecycle.py`
- **Changes**:
  - Removed aggressive truncation heuristics in `_trim_display_for_chat` that previously discarded markdown content after the first header or bullet list.
  - Completely uncoupled display text from voice collision trimming, ensuring canonical display text (`displayText`) is preserved unconditionally without destructive post-processing.
  - Conversational brevity is applied independently to `spokenText`.
  - Normalized evidence dictionary structures passed into `CitationRenderer` to prevent runtime `AttributeError`.
- **Verification**: All 13 tests in `apps/api/tests/test_response_quality.py` and 6 tests in `apps/api/tests/test_response_lifecycle.py` pass cleanly.

### 2. Code Block Indentation Preservation (Backtick & Tilde)
- **Affected Files**:
  - `apps/api/hinaa_api/services.py`
- **Changes**:
  - Implemented regex-based code fence splitting `(```[\w-]*|```|~~~[\w-]*|~~~)`.
  - Whitespace compression is strictly bypassed inside all code blocks (both backtick and tilde fences, language-tagged, and unfinished fences), preserving exact leading indentation and tabs.
- **Verification**: Verified via `test_preserves_code_indentation_inside_fences` in `test_response_quality.py` and `test_response_lifecycle_backtick_and_tilde_code_fences` in `test_response_lifecycle.py`.

### 3. Server-Owned Model Registry Upgrade
- **Affected Files**:
  - `apps/api/hinaa_api/harness/model_registry.py`
  - `apps/api/tests/test_hina_harness.py`
- **Changes**:
  - Registered verified operational specifications for production models: `gemini-2.5-flash`, `gemini-2.5-pro`, `claude-3-7-sonnet-20250219`, `llama-3.3-70b-versatile`, `gpt-4o`, `hinaa-mock-v1`.
  - Added verified context window and max output token bounds.
  - Validated multi-modal capabilities and tool-calling support.
- **Verification**: All 8 tests in `apps/api/tests/test_hina_harness.py` pass cleanly.

### 4. Provider Auto-Priority Resolution Fix
- **Affected Files**:
  - `apps/web/src/features/providers/utils/resolveProviderSelection.ts`
  - `apps/web/src/features/providers/utils/resolveProviderSelection.test.ts`
- **Changes**:
  - Restored canonical `AUTO_PRIORITY` hierarchy (`cx-gateway` -> `claude` -> `experiential` -> `codecraft` -> ... -> `real` -> `gemini-live`).
  - Preserved explicit user model selections while maintaining deterministic fallback logic.
- **Verification**: All 20 tests in `resolveProviderSelection.test.ts` pass cleanly.

### 5. Progressive Audio Lifecycle Hardening
- **Affected Files**:
  - `apps/web/src/design-system/modes/WorkMode.tsx`
- **Changes**:
  - Gated teletype sound execution (`playStreamChunkSound`) by active `speaking` or `thinking` state.
  - Audio feedback ceases immediately upon turn finalization, eliminating lingering typing clicks.
- **Verification**: Verified via frontend test suite (603 tests pass in `apps/web`).

### 6. Production Deployment Decoupling
- **Affected Files**:
  - `vercel.json`
  - `apps/web/vercel.json`
- **Changes**:
  - Removed temporary Cloudflare tunnel endpoints (`https://framed-parker-atm-consider.trycloudflare.com`).
  - Configured production upstream destination `https://hinaa-api.onrender.com` for `/api/*`, `/v1/*`, and health probes.
- **Verification**: Vercel configuration schemas validated; production rewrite routes verified.

### 7. Core Operational Documentation
- **Affected Files**:
  - `docs/architecture.md`
  - `docs/capability-matrix.md`
  - `docs/root-cause-analysis.md`
  - `docs/model-routing.md`
  - `docs/security-threat-model.md`
  - `docs/voice-state-machine.md`
  - `docs/deployment-runbook.md`
  - `docs/evaluation-report.md`
  - `docs/known-limitations.md`
  - `docs/upgrade-changelog.md`
- **Changes**:
  - Authored comprehensive documentation detailing system architecture, verified capabilities, root causes, security boundaries, and operational runbooks.

### 8. End-to-End Vertical Slice Verification
- **Affected Files**:
  - `apps/api/tests/test_vertical_slice_e2e.py`
- **Changes**:
  - Implemented end-to-end integration test validating authenticated turn orchestration, persistence, reload fidelity, tenant boundary isolation (second-user rejection), grounded RAG citation resolution, low-risk observable tool execution, turn cancellation, and honest recoverable provider errors.
- **Verification**: Verified via `pytest apps/api/tests/test_vertical_slice_e2e.py`.
