# HINAA Change Manifest

> **Safety checkpoint:** `checkpoint/hinaa-evidence-plan-20260812T064546Z` at `a1481389a9debce4a7f89a01cc9d7d00367fd80c`.
>
> This manifest records only changes made during the approved runtime-evidence plan. Environment files, secrets, VRM binaries, and ComfyUI model files are excluded.

| File path | Reason for modification | System affected | Regression risk | Tests performed | Result |
|---|---|---|---|---|---|
| `docs/HINAA_CHANGE_MANIFEST.md` | Create a reviewable change/evidence ledger before implementation. | Repository governance | None | Baseline Git status and safety tag recorded. | Complete |
| `docs/HINAA_CURRENT_STATUS.md` | Track phase evidence, verified outcomes, and concrete blocks. | Runtime verification | None | Baseline services and repository recorded. | Complete |

## Update Rules

For every subsequent changed file, add a row before publishing the related phase. Record the focused regression test or real runtime scenario and its outcome. A blocked external dependency must be labeled **BLOCKED** with the exact reason; it must never be represented as passed.
| `apps/web/src/features/companion/useCompanionController.ts` | Add an idempotent sequence-aware terminal finalizer and apply immediate recovery to browser and live-stream errors/completions. | Conversation controller, composer recovery, live chat | Medium: terminal state ordering and message lifecycle | TypeScript type-check passed; real browser test: OpenAI `PROVIDER_KEY_INVALID` then Demo success without refresh; a broad Vitest run was stopped only after sandbox memory pressure. | Runtime recovery VERIFIED; focused type check PASSED. |
| `docs/HINAA_CURRENT_STATUS.md` | Record controlled provider failure and same-session successful recovery evidence. | Runtime verification | None | Live browser scenario, timestamps, transcript, header status, and composer visibility inspected. | VERIFIED. |
| `apps/web/src/features/companion/assistantTurnCodec.ts` | Add one schema-backed serializer/decoder for structured assistant turns, display text, spoken text, and tool artifacts. | Transcript persistence and TTS boundary | Low: legacy history handling | Codec regression suite: structured round-trip, legacy text, malformed payload, separate speech, retained artifacts. | PASSED. |
| `apps/web/src/features/companion/assistantTurnCodec.test.ts` | Cover canonical response persistence and safe restoration. | Regression coverage | None | Vitest completed: 20 files, 96 tests passing. | PASSED. |
| `apps/web/src/features/companion/types.ts` | Store optional canonical assistant content alongside existing text and plan fields. | Transcript contract | Low | TypeScript type-check passed. | PASSED. |
| `apps/web/src/features/companion/useCompanionController.ts` | Serialize plans on creation and decode saved transcript messages on restore. | Conversation controller and refresh persistence | Medium | TypeScript type-check passed; codec regression run passed. | PASSED. |
| `apps/api/hinaa_api/services.py` | Replace broad keyword fallback with explicit command classification and route known simple web destinations through the current direct navigation tool. | Tool routing and approval-ready browser actions | Medium: command parsing and tool selection | `pytest tests/test_conversation_brain.py -q` passed (9 tests); real `Open Netflix` equivalent produced one owned page. | VERIFIED. |
| `apps/api/hinaa_api/tools/browser_automation.py` | Reuse installed Chromium when available and report the owned page count after direct navigation. | Existing browser owner | Medium: local Chromium launch behavior | Real confirmed navigation returned Netflix title and `Owned browser pages: 1`. | VERIFIED. |
| `apps/api/tests/test_conversation_brain.py` | Test imperative image/browser/research commands and non-execution framing cases, including exact Netflix URL. | Tool-routing regression coverage | Low | `pytest tests/test_conversation_brain.py -q`: 9 passed. | PASSED. |
| `apps/web/src/features/providers/mockConversationProvider.ts` | Return dedicated, concise-speech Hindi and Nepali ComfyUI guidance in native Devanagari scripts ahead of generic mock fallback. | Demo conversation provider and language presentation | Low: Demo response selection only | Live chat completed both required prompts; full Vitest suite passed (20 files, 97 tests). | VERIFIED (text). |
| `apps/web/src/features/providers/mockConversationProvider.test.ts` | Add Hindi and Nepali grammar regression coverage, including readable English technical terms and concise spoken summaries. | Language quality regression coverage | None | Full Vitest suite passed: 20 files, 97 tests, 2 existing todos. | PASSED. |
| `docs/HINAA_CURRENT_STATUS.md` | Record post-reload Hindi/Nepali live evidence, TTS credential limitation, and completed regression suite results. | Runtime verification dossier | None | Browser transcript inspected; TypeScript check passed; API suite passed with 165 tests. | VERIFIED / BLOCKERS DISCLOSED. |
