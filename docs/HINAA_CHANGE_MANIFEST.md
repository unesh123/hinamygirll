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
| `apps/web/src/App.tsx` | Persist the selected approved Hinaa VRM URL locally, validate it against the two allowed models, and restore it at application startup. | Avatar selector and local preference storage | Low: invalid/stale storage values fall back to model_6164. | Focused App remount test, full Vitest suite, type check, production build, and live select/reload inspection. | VERIFIED. |
| `apps/web/src/App.test.tsx` | Assert that selecting Hinaa Classic writes the local preference and restores the active selector after remount. | Avatar persistence regression coverage | None | Full Vitest suite passed: 20 files, 99 tests, 2 existing todos. | PASSED. |
| `apps/web/src/features/providers/mockConversationProvider.ts` | Add a structured React Server Components professional-answer path with separate short plain spoken text. | Demo conversation response quality and speech boundary | Low: deterministic Demo response only. | Provider regression, full Vitest suite, type check, production build. | VERIFIED (Demo contract). |
| `apps/web/src/features/providers/mockConversationProvider.test.ts` | Assert detailed RSC sections/code in display text and Markdown-free concise speech. | Professional-answer regression coverage | None | Full Vitest suite passed: 20 files, 99 tests, 2 existing todos. | PASSED. |
| `apps/api/hinaa_api/config.py` | Move the unset local database default from volatile memory to `~/.hinaa/hinaa.db`. | Local persistence and restart durability | Medium: first start creates a private database file. | Config regression, full API suite, live API restart and project persistence check. | VERIFIED. |
| `apps/api/hinaa_api/persistence/db.py` | Create the parent directory for a file-backed SQLite URL before opening the engine. | Durable private SQLite startup | Low: in-memory test URLs remain unchanged. | Full API suite and live local API restart. | PASSED. |
| `apps/api/hinaa_api/persistence/orm.py` | Remove the placeholder `local-user` default so local projects require an explicit owner. | Project ownership integrity | Medium: any new direct ORM construction must provide an owner. | New ownership regression and live database inspection. | VERIFIED. |
| `apps/api/tests/test_config.py` | Protect the private durable SQLite database default against reversion to in-memory storage. | Configuration regression coverage | None | Full API suite passed. | PASSED. |
| `apps/api/tests/test_local_workspace.py` | Directly inspect created project rows to prove the resolved owner is used and the removed placeholder is not. | Ownership regression coverage | None | Focused workspace suite (5 passed) and full API suite passed. | PASSED. |
| `docs/HINAA_CURRENT_STATUS.md` | Record durable project recovery, avatar refresh persistence, owner integrity, local release validation, and remaining external blocks. | Final runtime evidence dossier | None | Live API/browser evidence and final test/build validation recorded. | VERIFIED / BLOCKERS DISCLOSED. |
| `apps/web/src/App.tsx` | Replace the silent Demo-mode speech return with a browser voice fallback; redirect placeholder/cloud failures to intelligible device speech and track the visible voice route. | Completed chat turn and audio playback | Low: browser speech is used only when no real intelligible provider is available. | Full frontend suite, live Demo turn, type check, production build. | VERIFIED. |
| `apps/web/src/features/audio/useAudioPlayback.ts` | Add device `speechSynthesis` playback, text-derived visemes, replay, mute-aware stopping, and cleanup. | Local browser voice and avatar lip-sync | Medium: browser voice quality depends on the user’s installed system voices. | New deterministic hook regression and live browser Demo turn. | VERIFIED (local browser route). |
| `apps/web/src/features/audio/useAudioPlayback.test.ts` | Assert device speech starts, exposes speaking/viseme state, and finishes cleanly. | Local fallback regression coverage | None | Full frontend suite: 21 files, 101 passing tests, 2 existing todos. | PASSED. |
| `apps/web/src/features/audio/useLiveConversation.ts` | Replace realtime mock/placeholder audio cues with one final intelligible browser-spoken response. | Microphone live conversation audio path | Low: only providers marked mock/placeholder are redirected. | Type check and full frontend suite. | VERIFIED by regression/implementation; physical microphone requires user hardware. |
| `apps/web/src/components/ui/PremiumComposer.tsx` | Add concise voice route feedback plus accessible replay and mute controls. | Chat composer user experience | Low | Full frontend suite and live workspace inspection. | VERIFIED. |
| `apps/web/src/App.css` | Style voice status, route indicator, replay, and mute affordances responsively. | Chat composer visual polish | Low | Production build and live workspace inspection. | VERIFIED. |
| `apps/web/src/App.test.tsx` | Keep the local voice control accessible through app-shell changes. | UI regression coverage | None | Full frontend suite passed. | PASSED. |
| `apps/web/src/features/settings/sections/ProviderSettings.tsx` | Surface safe device-fallback status and backend-only ElevenLabs variable guidance without exposing secrets. | Provider settings UX | Low | Live Settings panel inspection and frontend suite. | VERIFIED. |
| `apps/api/hinaa_api/providers/elevenlabs.py` | Remove the hard-coded Hindi constraint for multilingual v2 and use text-aware language hints only for compatible models. | ElevenLabs multilingual request correctness | Low: configured multilingual v2 request no longer sends an unsupported field. | Offline ElevenLabs unit suite and full API suite. | VERIFIED. |
| `apps/api/tests/test_elevenlabs_unit.py` | Assert English, Hindi, and Nepali language-hint selection. | ElevenLabs multilingual regression coverage | None | Focused ElevenLabs suite and full API suite passed. | PASSED. |
| `docs/HINAA_CURRENT_STATUS.md` | Record voice root cause, live fallback evidence, UI evidence, cloud-credential blockers, and final validation. | Runtime evidence dossier | None | Browser, API, test, and build evidence recorded. | VERIFIED / BLOCKERS DISCLOSED. |
| `apps/web/src/features/companion/useCompanionController.ts` | Delay turn finalization until trailing stream metadata completes; return immutable turn ID and resolve the active typed-turn locale. | Typed chat recovery, canonical turn handoff, voice lifecycle | Medium: preserves composer recovery while extending lifetime only through the provider stream. | Typed Demo voice acceptance regression; full frontend suite. | INTEGRATION_TESTED. |
| `apps/web/src/App.tsx` | Add one-active-session typed playback ownership, stale-session interruption, completed-state tracking, and settings-driven language policy wiring. | Typed speech, composer, avatar voice presentation | Medium: prevents duplicate/stale playback and makes session termination observable. | App voice acceptance regression, type check, production build. | INTEGRATION_TESTED. |
| `apps/web/src/features/providers/conversationProvider.ts` | Add explicit resolved locale to the provider request contract. | Provider routing | Low | Type check and full frontend suite. | PASSED. |
| `apps/web/src/features/providers/backendConversationProvider.ts` | Send the resolved HINAA locale instead of unrestricted `mixed` for typed backend turns. | Backend typed-turn transport | Low | Type check and provider regression suite. | PASSED. |
| `apps/web/src/features/providers/mockConversationProvider.ts` | Enforce strict Hindi Devanagari or English normal Demo responses; keep Nepali only for explicit experimental locale requests. | Active product language policy | Medium: changes Demo copy by explicit product request while retaining Nepali implementation. | 7 provider tests including Hindi, disabled normal Nepali, and experimental Nepali. | PASSED. |
| `apps/web/src/features/providers/mockConversationProvider.test.ts` | Preserve Nepali coverage behind explicit experimental locale and protect strict Hindi fallback behavior. | Language regression coverage | None | Full frontend suite passed. | PASSED. |
| `apps/web/src/features/settings/types/settings.ts` | Add version-3 persisted active language policy, defaulting to Auto Hindi / English. | Local settings schema | Low: versioned migration provides the missing field. | Settings migration regression and type check. | PASSED. |
| `apps/web/src/features/settings/state/settingsStore.ts` | Migrate prior settings to the Hindi/English auto policy and validate all supported language options. | Local settings persistence | Low | Settings regression and full frontend suite. | PASSED. |
| `apps/web/src/features/settings/hooks/useSettings.ts` | Add type-safe language preference updates using existing persistence. | Settings behavior | Low | Type check and frontend suite. | PASSED. |
| `apps/web/src/features/settings/sections/LanguageSettings.tsx` | Add the focused language settings UI, marking Nepali as experimental. | Settings UI | Low | Production frontend build and type check. | IMPLEMENTED. |
| `apps/web/src/features/audio/useLiveConversation.ts` | Remove the hard-coded Nepali realtime session bias and derive hello locale from active policy. | Live voice language routing | Medium: mixed auto still relies on provider language detection. | Type check and full frontend suite. | IMPLEMENTED. |
| `apps/api/hinaa_api/config.py` | Require both AgentRouter key and base URL to report configured state. | Provider configuration integrity | Low | Focused and complete backend regression suites. | PASSED. |
| `apps/api/hinaa_api/main.py` | Add secret-safe ElevenLabs diagnostics and correct the AgentRouter requirements message. | API diagnostics and provider UX | Low: no provider call is made by diagnostics. | API diagnostics/config tests and runtime endpoint query. | INTEGRATION_TESTED. |
| `apps/api/tests/test_api.py` | Assert secret-safe voice diagnostics reveal no credential while accurately reporting missing configuration. | API regression coverage | None | Focused and complete backend suites passed. | PASSED. |
| `apps/api/tests/test_config.py` | Assert AgentRouter requires both its key and base URL. | Configuration regression coverage | None | Focused and complete backend suites passed. | PASSED. |
| `docs/HINAA_CURRENT_STATUS.md` | Record baseline preservation, typed-turn race proof, language policy, provider evidence, ComfyUI blocker, and final validation. | Runtime evidence dossier | None | Evidence recorded from tests, API, and safe local service probes. | UPDATED. |
| `apps/web/src/components/ui/AvatarPresence.tsx` | Derive portrait/closeup/full camera configuration from each loaded VRM’s head, chest, and bounds; reset anatomy on model change. | 3D avatar framing | Medium: camera transform changes by model | TypeScript check and full frontend suite completed; source retains calibrated non-limb VMC safety. | PASSED / implementation verified by regression build. |
| `apps/web/src/features/chat/components/MessageBubble.tsx` | Guard empty assistant tool-request arrays explicitly so JavaScript numeric falsiness cannot render stray `0`. | Transcript rendering | Low | New focused component regression and complete frontend suite. | PASSED. |
| `apps/web/src/features/chat/components/MessageBubble.test.tsx` | Add coverage for the empty-tool-list stray-zero defect. | Chat regression coverage | None | `pnpm test -- --run`: 23 files, 106 passing tests, 2 existing todos. | PASSED. |
| `apps/api/hinaa_api/tools/image_generate.py` | Honor user seed, terminate no-output/worker-failure slots truthfully, constrain mode, and require an explicitly resolved user for durable generation ownership. | Local ComfyUI queue and durable ownership | Medium: tool payload validation and terminal statuses | Complete backend suite; read-only SQLite audit; final API restart. | PASSED. |
| `apps/api/hinaa_api/main.py` | Return ordered progressive image slots, safe URLs, seeds, completion count, and partial-success state from the existing poll endpoint. | Image job polling API | Low: additive response metadata | Frontend progressive-slot regression, complete backend suite, final API restart. | PASSED. |
| `apps/web/src/components/ui/LocalImageStudio.tsx` | Render all requested sequential slots immediately, replace each slot as its local image arrives, expose seed, and retain partial results. | Local Image Studio UX | Low | New component regression, type check, full frontend suite, production build. | PASSED. |
| `apps/web/src/components/ui/LocalImageStudio.test.tsx` | Verify image 1 becomes visible before image 2 finishes and seed is forwarded. | Image Studio regression coverage | None | Focused and complete frontend suite: 23 files, 106 passing tests. | PASSED. |
| `apps/api/hinaa_api/vmc_bridge.py` | Inspected without source modification; verified existing singleton UDP listener and blendshape WebSocket transport. | Local VSeeFace/VMC path | None | Live `Fcl_MTH_Open=0.62` UDP-to-WebSocket probe before and after final API restart. | VERIFIED. |
| `apps/web/src/features/audio/useVSeeFace.ts` | Inspected without source modification; verified explicit browser tracking lifecycle and state reset boundary. | VSeeFace browser client | None | Source review plus live local bridge probe. | VERIFIED transport; physical VSeeFace sender unavailable. |
| `docs/HINAA_VMC_CHANGELOG.md` | Replace pending VMC note with support boundary and exact model/process blocks. | VMC evidence ledger | None | Local transport probe and asset/process inspection. | UPDATED / truthful limits recorded. |
| `docs/HINAA_COMPLETION_CHANGELOG.md` | Record final completion changes, runtime evidence, and unresolved dependencies. | Completion ledger | None | Final validation review. | UPDATED. |
| `docs/HINAA_CURRENT_STATUS.md` | Record final image, VMC, ownership, and release evidence. | Runtime evidence ledger | None | Final validation review. | UPDATED. |
| `docs/HINAA_CHANGE_MANIFEST.md` | Append this completion-pass review trail. | Repository governance | None | Git diff review before isolated checkpoint. | UPDATED. |


## Windows Avatar, VSeeFace, VMC, and Live-Presence Completion — 2026-08-13

| File | Change reason | System | Risk control | Verification | Result |
|---|---|---|---|---|---|
| `apps/api/hinaa_api/vmc_bridge.py` | Extend the existing single VMC bridge with source/timestamp/rate/channel diagnostics and a clearly labelled test injection. | Local VMC transport | No second UDP bridge; synthetic source cannot become `live`; continuous external stream threshold required. | Focused bridge tests; runtime listening/test/stale probe. | **PASS** |
| `apps/api/hinaa_api/main.py` | Expose local VMC diagnostics/test action and private managed avatar inventory/import/file/delete routes. | Local API | Approved roots only, opaque IDs, path-safe delivery, parse validation, explicit delete confirmation. | Full API regression; runtime endpoint checks. | **PASS** |
| `apps/api/hinaa_api/avatar_assets.py` | Provide parse-based VRM/glTF inventory and managed import/delete service. | Local avatar asset management | Never rewrites original file; detects VRM extension version rather than filename; no arbitrary filesystem API. | Avatar parser regression. | **PASS** |
| `apps/api/tests/test_vmc_and_avatar_assets.py` | Cover VMC listening/test/live/stale distinctions and VRM 0.x/1.0 compatibility boundary. | API regression | Unit fixture only; no real-camera claim. | Focused `pytest`. | **PASS** |
| `apps/web/src/features/audio/useVSeeFace.ts` | Replace WebSocket-open-as-live behavior with diagnostics-driven idempotent client and live-only calibration. | Browser VMC consumer | Transport connection is never live evidence; packet refs limit render pressure. | Type check; full frontend tests. | **PASS** |
| `apps/web/src/components/ui/VmcControlPanel.tsx` | Make LIVE control actionable with diagnostics, state feedback, safe retry/test/calibration actions. | Avatar UI | Test fixture is visibly labelled; neutral calibration requires live external state. | Component regression. | **PASS** |
| `apps/web/src/components/ui/VmcControlPanel.test.tsx` | Prevent listener state from regressing to a false LIVE claim. | Frontend regression | Asserts listener copy and disabled calibration. | Vitest. | **PASS** |
| `apps/web/src/components/ui/AvatarLab.tsx` | Add in-app Avatar Lab drawer with safe inventory/import/delete/model/camera/strategy controls. | Avatar UI | No second canvas; no unverified model status claim; confirmation before managed-copy deletion. | Type check and production build. | **PASS** |
| `apps/web/src/components/ui/AvatarPresence.tsx` | Repair anatomy-aware portrait framing, explicit camera set, central rest-relative pose profile, and calibrated head-only VMC response. | Active single avatar renderer | Unknown assets retain rest pose; TTS owns mouth during speech; no limb driving; 22° head bound. | Type check and production build. | **PASS** |
| `apps/web/src/App.tsx` | Wire truthful status, Avatar Lab, explicit strategy mode, managed selection, and per-model camera persistence. | Application shell | Existing one avatar renderer retained; only fresh external state reaches face driver. | Type check; frontend regression. | **PASS** |
| `apps/web/src/components/ui/NavRail.tsx` | Add explicit accessible labels/titles to all rail buttons. | Navigation accessibility | Existing navigation callbacks preserved. | Full frontend regression. | **PASS** |
| `docs/HINAA_AVATAR_VMC_WINDOWS_CHANGELOG.md` | Record baseline, audit, implementation evidence, and Windows-runtime blockers. | Evidence ledger | Distinguishes implementation from real Windows verification. | Repository review. | **PASS** |
| `docs/HINAA_WINDOWS_VRM_ASSET_INVENTORY.md` | Record approved root policy and parse-derived asset findings. | Asset evidence | Never treats sandbox asset result as user Windows filesystem result. | Runtime inventory response. | **PASS** |
| `docs/HINAA_SIDEBAR_CAPABILITY_MATRIX.md` | Document active/degraded/blocked sidebar behavior and accessibility changes. | UX evidence | No capability inferred from icon appearance. | Source audit. | **PASS** |


## VSeeFace Control Panel Visibility Hotfix — 2026-08-13

| File | Change reason | System | Risk control | Verification | Result |
|---|---|---|---|---|---|
| `apps/web/src/App.css` | Add missing fixed portal overlay, stacking, panel, pointer-event, responsive, header, close, and scroll rules for `HinaDrawer`. | VSeeFace / Avatar Lab panel presentation | Reuses the existing portal/drawer and does not alter VMC data, model binaries, or credentials. | App-level VSeeFace dialog regression; production build. | **PASS** |
| `apps/web/src/App.test.tsx` | Assert the actual avatar VSeeFace pill opens the portal-mounted VMC control panel and shows its initial disconnected guidance. | App-shell regression | Prevents an icon-only/no-visible-panel regression. | Full frontend suite: 24 files, 108 tests passing, 2 existing todos. | **PASS** |
| `docs/HINAA_AVATAR_VMC_WINDOWS_CHANGELOG.md` | Record no-op root cause, repair, test evidence, and My Browser automation limitation. | Evidence ledger | Separates UI repair evidence from external tracking evidence. | Repository review. | **UPDATED** |
| `docs/HINAA_CURRENT_STATUS.md` | Record the hotfix release gates and exact unresolved Windows sender/model boundary. | Runtime status ledger | Does not claim a browser-extension timeout proves or disproves app tracking. | Repository review. | **UPDATED** |
| `docs/HINAA_CHANGE_MANIFEST.md` | Append the hotfix review trail. | Repository governance | No protected asset or secret is included. | Diff review before checkpoint. | **UPDATED** |


## Simple Avatar Workflow and Per-Model Presentation — 2026-08-13

| File | Change reason | System | Risk control | Verification | Result |
|---|---|---|---|---|---|
| `apps/web/src/features/avatar/avatarPresentation.ts` | Persist per-model browser-only facing, position, scale, and relaxed/original pose state. | Avatar presentation | Bounded values; no binary mutation; stored by model URL. | Focused persistence/bounds/facing test. | **PASS** |
| `apps/web/src/features/avatar/avatarPresentation.test.ts` | Prevent regressions in imported-model default facing, relaxed pose, correction, bounds, and persistence. | Frontend regression | No model file required. | 4 tests passed. | **PASS** |
| `apps/web/src/components/ui/AvatarPresence.tsx` | Apply the selected model’s persisted browser presentation and conservative normalized-bone relaxed profile; allow author-pose recovery. | Active single renderer | One renderer only; no raw nodes/cumulative transforms/binary writes. | Type check and full frontend suite. | **PASS** |
| `apps/web/src/App.tsx` | Add direct upload-and-select avatar action and wire per-model presentation state into the existing Avatar Lab and renderer. | App shell | Reuses managed local import API and opaque asset URL; rejected B/C choices stay absent. | App upload/select regression. | **PASS** |
| `apps/web/src/App.test.tsx` | Cover direct local file import → managed URL selection and clear status feedback; retain selector persistence proof. | App regression | Mocked API response only, no user file is read in tests. | Full frontend suite. | **PASS** |
| `apps/web/src/components/ui/AvatarLab.tsx` | Replace dense technical model workflow with HINAA-themed upload/select, facing/arm/reset, camera, and safe tracking choices. | Avatar Lab UI | Exact VSeeFace remains version-gated; tracking proxy remains labelled. | Type check and production build. | **PASS** |
| `apps/web/src/App.css` | Add HINAA mint/pearl responsive Avatar Lab and direct-upload selector styling. | UI polish | Does not alter global VMC protocol or original assets. | Production build. | **PASS** |
| `docs/HINAA_AVATAR_VMC_WINDOWS_CHANGELOG.md` | Record behavior, evidence, and browser-extension limitation. | Evidence ledger | Keeps model-specific visual verification separate from source verification. | Repository review. | **UPDATED** |


## Final Local-Agent Product Polish — 2026-08-13

| File | Change reason | System | Risk control | Verification | Result |
|---|---|---|---|---|---|
| `apps/web/src/components/ui/SidebarPanel.tsx` | Replace fabricated histories, fake tasks/files, and guessed tool readiness with direct local HINAA actions and truthful guidance. | Sidebar / agent UX | Every visible action maps to an existing callback; no provider or tool is labelled ready without runtime evidence. | Focused sidebar regression. | **PASS** |
| `apps/web/src/App.tsx` | Wire sidebar actions to real new-chat, voice, memory, image, projects, settings, and prompt-preparation paths. | Application shell | Existing confirmations and provider routing remain owned by current components. | Type check and full suite. | **PASS** |
| `apps/web/src/App.css` | Add responsive, keyboard-focused, HINAA-themed shortcut panel styling. | Accessibility / responsive UI | Reuses existing design tokens and reduced-motion behavior. | Production build. | **PASS** |
| `apps/web/src/components/ui/SidebarPanel.test.tsx` | Prove tools and chat panels offer real callbacks and no longer show fabricated readiness/history. | Frontend regression | Mock callbacks only; no external action. | 2 tests passed. | **PASS** |
| `apps/web/src/components/ui/ContextWorkspace.tsx` | Replace generic image empty state with truthful mode-specific research, image, music, email, and browser guidance. | State clarity | External actions remain explicitly described as approval/configuration-dependent. | Focused context regression. | **PASS** |
| `apps/web/src/components/ui/ContextWorkspace.test.tsx` | Prevent a return to generic or misleading workspace empty states. | Frontend regression | No provider/browser dependency. | 1 test passed. | **PASS** |
| `docs/HINAA_COMPLETION_CHANGELOG.md` | Record final local-agent polish and release evidence. | Completion ledger | Distinguishes code verification from unavailable runtime integrations. | Repository review. | **UPDATED** |
| `docs/HINAA_CHANGE_MANIFEST.md` | Append this reviewable final-polish trail. | Repository governance | No protected asset or secret included. | Diff review before checkpoint. | **UPDATED** |


## Screenshot-Driven Safe VSeeFace Tracking Repair — 2026-08-13

| File | Change reason | System | Risk control | Verification | Result |
|---|---|---|---|---|---|
| `apps/web/src/components/ui/AvatarPresence.tsx` | Correct VMC eye closure consumption and execute VRM update before the final safe head/relaxed-arm pose layer. | Active single VRM renderer | VMC body transforms remain ignored; head needs neutral calibration; TTS keeps mouth ownership when speaking; no model binary changes. | Type check and VMC/app regression suite. | **PASS** |
| `apps/web/src/features/audio/useVSeeFace.ts` | Initialize VMC eye closure samples as open (`0`) to match `Fcl_EYE_Close` semantics. | Browser tracking client | Per-packet values remain clamped and refs avoid React render-rate motion updates. | Type check. | **PASS** |
| `apps/api/hinaa_api/vmc_bridge.py` | Initialize bridge eye closure values as open (`0`) with explicit semantic documentation. | Singleton VMC bridge | No protocol/new receiver changes; existing source/rate/live safeguards retained. | Focused bridge suite. | **PASS** |
| `apps/api/tests/test_vmc_and_avatar_assets.py` | Add regression for VMC open-eye defaults and close-weight preservation. | Backend regression | No real camera/model dependency. | 3 focused tests passed. | **PASS** |
| `apps/web/src/components/ui/VmcControlPanel.tsx` | State clearly that live VMC controls face/calibrated head while body and arms remain protected. | User-visible tracking controls | Prevents misleading full-body-mirroring expectation. | VMC panel regression preserved. | **PASS** |
| `docs/HINAA_AVATAR_VMC_WINDOWS_CHANGELOG.md` | Record user-screenshot defect, source cause, repair, and Windows visual-verification boundary. | Evidence ledger | Does not label a screenshot-derived repair as verified real camera motion. | Repository review. | **UPDATED** |


## Companion Playground and Smooth Expression Pass — 2026-08-13

| File | Change reason | System | Risk control | Verification | Result |
|---|---|---|---|---|---|
| `apps/web/src/components/ui/AvatarPresence.tsx` | Use shoulder-aware relaxed profiles calibrated from the shipped VRM hierarchy; widen companion framing; add the existing canvas’s native fullscreen playground control; smooth live face samples; blend restrained HINAA reply-text emotion cues. | Single avatar renderer | No additional canvas or binary edit; body VMC remains ignored; head stays calibration-bounded; TTS owns mouth while speaking. | Full frontend release gates. | **PASS** |
| `apps/web/src/App.tsx` | Pass only HINAA’s latest assistant reply into the expression director and gate facial expression values on actual detected blendshape channels. | App shell | Never classifies user/camera emotion; fresh motion without expressions is visibly degraded rather than falsely mirrored. | Type check and app regressions. | **PASS** |
| `apps/web/src/App.css` | Enlarge desktop companion stage and style the existing fullscreen playground accessibly and responsively. | UI polish | Retains one canvas and mobile layout; reduced-motion policy preserved. | Production build. | **PASS** |
| `apps/web/src/features/avatar/companionExpression.ts` | Add deterministic multilingual reply-text expression intent selection. | Expression director | Fixed local pattern mapping only; no external model/camera analysis. | 3 unit tests. | **PASS** |
| `apps/web/src/features/avatar/companionExpression.test.ts` | Cover celebratory English/Devanagari, empathy, concern, and neutral warm behavior. | Frontend regression | No media or provider dependency. | 3 tests passed. | **PASS** |
| `apps/web/src/features/audio/useVSeeFace.ts` | Expose `hasFacialSignal` from observed bridge channels. | Tracking state | Transport state is distinct from expression readiness. | VMC control regressions. | **PASS** |
| `apps/web/src/components/ui/VmcControlPanel.tsx` | Show face-signal readiness and truthful waiting guidance in the existing VMC panel. | User-visible diagnostics | Does not imply facial tracking without a detected channel. | 2 panel tests. | **PASS** |
| `apps/web/src/components/ui/VmcControlPanel.test.tsx` | Cover live motion packets without blendshape readiness. | Frontend regression | Mocked diagnostics only. | **PASS** |
| `docs/HINAA_AVATAR_VMC_WINDOWS_CHANGELOG.md` | Record source findings, implementation, release gates, and real-runtime boundary. | Evidence ledger | Source verification is separate from Windows visual proof. | Updated. | **UPDATED** |

## Phase 20 — High-Presence Jarvis UI, Streaming Voice, and Hindi-English Contract — 2026-08-13

| File or area | Change | Acceptance evidence |
|---|---|---|
| `docs/HINAA_PRODUCT_DESIGN.md` | Added the project-scoped Ink Rose companion design system informed by the requested Taste, Impeccable, and 21st.dev interaction guidance. | Design brief includes source references. |
| `apps/web/index.html`, `apps/web/src/App.css` | Replaced the conflicting bright mint/cyan/lavender shell with the Ink Rose palette, Outfit/JetBrains Mono hierarchy, accessible surface contrast, responsive motion, and reduced-motion behavior. | Frontend suite, type check, and Vite/PWA build pass. |
| `apps/web/src/components/ui/VmcControlPanel.tsx` | Replaced dense raw diagnostics with guided local receiver, sender-observed, and neutral-capture stages; advanced details remain progressive. | VMC and app drawer regressions pass. |
| `apps/api/hinaa_api/realtime.py`, `apps/web/src/features/audio/useLiveConversation.ts` | Real configured providers deliver ordered stable phrase audio during text streaming, including sanitized segment text for exact playback and lip-sync. | Realtime, voice, frontend audio, and full release suites pass. |
| `apps/web/src/components/ui/AvatarPresence.tsx`, `apps/web/src/features/audio/useVSeeFace.ts` | Full neutral facial baseline capture prevents a sender’s resting mouth/vowel offsets from opening HINAA’s mouth. TTS retains mouth ownership while speaking. | Avatar/VMC/audio regressions and typed build pass; real Windows proof remains required. |
| `apps/web/src/components/ui/LocalImageStudio.tsx` | Re-themed the existing explicit ComfyUI check, local status, sequential slots, and multi-output controls without fabricating a running service. | Sequential-slot regression passes. |
| `apps/web/src/features/settings/**`, `apps/web/src/features/companion/useCompanionController.ts`, `apps/web/src/features/providers/mockConversationProvider.ts` | Retired normal Nepali routing; persisted settings migrate to automatic Hindi-English and active UI, voice, and Demo behavior use Devanagari Hindi and English only. | Settings, Demo, live audio, and type regressions pass. |
| `apps/api/hinaa_api/{config,models,prompts,voice_performance,voice_profiles}.py`, realtime schema and corpus | Replaced retired Nepali defaults, prompt instructions, locales, voice metadata, schema values, and offline fixtures with Hindi-English equivalents. Default Azure metadata is `hi-IN-SwaraNeural` / `hi-IN-MadhurNeural`; actual cloud audio remains credential-dependent. | Complete backend pytest suite passes. |

No original VRM binary, ComfyUI model/workflow, secret, SQLite database, generated media, or Windows-local user file is included. `main` remains untouched.

## Visual Polish Pass — Screenshot-Driven Workspace Refinement — 2026-08-13

| File or area | Change | Acceptance evidence |
|---|---|---|
| `apps/web/src/App.css` | Reworked the desktop shell above the aura layer; introduced premium Ink Rose rail, avatar stage, model dock, header, reading surface, composer, and compact avatar-control treatment. | Two local 1600×960 headless visual renders; follow-up confirms readable shell/control hierarchy. Frontend suite, type check, and production build pass. |
| `apps/web/src/features/chat/components/MessageBubble.module.css` | Replaced legacy dark-on-dark assistant text and mint/cyan user capsules with high-contrast assistant document surfaces, deep rose user turns, readable timestamps, thinking feedback, and reduced-motion-safe streaming. | Message bubble and full frontend regression suite pass. |
| `apps/web/src/features/chat/components/TranscriptView.module.css` | Reworked transcript scaffold, dividers, empty state, cards, scrollbar, and latest action into the Ink Rose system. | Local desktop visual render and frontend suite pass. |
| `apps/web/src/features/chat/components/MessageBubble.tsx` | Removed legacy purple/teal inline rich-text and blue-gray thinking accents in favor of high-contrast rose-compatible output. | TypeScript and component regression pass. |
| `apps/web/src/components/ui/NavRail.tsx` | Replaced legacy inline mint/cyan/white surfaces with semantic class-based HINAA navigation markup, preserving buttons, labels, tooltips, and keyboard targets. | App shell regression and frontend suite pass. |
| `apps/web/src/components/ui/AvatarPresence.tsx` | Re-themed only the existing single avatar playground backdrop, lights, fallback, live badge, fullscreen, and camera controls; no VRM model binary or second canvas was added. | TypeScript and avatar/app regressions pass. Windows avatar visual proof remains separate. |
| `docs/HINAA_PRODUCT_DESIGN.md`, `docs/HINAA_VISUAL_POLISH_EVIDENCE_2026-08-13.md` | Recorded screenshot-driven visual targets and two-pass local visual evidence, including the aura stacking diagnosis and explicit VRM visual verification boundary. | Evidence files added. |

No VRM binary, secret, local database, generated media, or ComfyUI asset is included. This pass remains on an isolated branch and does not merge `main`.


## Phase 22 — You.com real-time web intelligence

| Surface | Change | Verification |
|---|---|---|
| Private configuration | Added server-only `YDC_API_KEY`, verified You.com endpoint overrides, readiness state, and a safe `.env.example` entry. The key is never sent to Vite/browser code or committed. | Configuration-only provider-health regression passes. |
| Grounded tools | Replaced the key-configured web-search path with You.com real-time search and added explicit approval-gated tools for cited answers, selected URL contents, cited research, background research status, and opt-in finance research. | Mocked HTTP client regressions cover request normalization, source cards, key non-disclosure, private URL rejection, and confirmation gates. |
| Agent workflow | CX remains HINAA’s conversation brain. The deterministic router proposes a tool only for unambiguous user commands; normal chat never silently spends paid web credits. | Conversation routing regressions pass for every new command and for no-side-effect framing. |
| Citation and cost contract | Source cards retain a title, URL, bounded snippet, stable ID, and provider mode. Search defaults to five current sources, research defaults to `lite`, and expensive research levels are visible before approval. | Complete backend and frontend release gates pass. |

The current sandbox does not contain `apps/api/.env.local`, so live paid-key validation was intentionally not simulated or claimed. The user’s Windows-local runtime must restart after adding `YDC_API_KEY` and perform an explicitly approved search to validate the account and available credit.


## Phase 23 — Verified YouTube playback

| Surface | Change | Verification |
|---|---|---|
| `apps/api/hinaa_api/tools/youtube.py` | Removed `yt-dlp` and unowned `webbrowser.open()` playback claims. The tool now reuses HINAA’s single owned Playwright page, opens one first-party watch result in the same tab, attempts player start, and returns success only when unpaused ready media time advances across two observations. | Backend YouTube regression covers first-party URL filtering, advancing-media evidence, one-page verified success, blocked media, and confirmation gating. |
| `apps/web/src/features/tools/toolOutcome.ts` | Added a single result interpreter that distinguishes HTTP/tool completion from verified user-goal completion. | Frontend regression proves YouTube is complete only with `verified: true`; optimistic or blocked payloads stay incomplete. |
| `apps/web/src/features/companion/useCompanionController.ts` and `apps/web/src/features/tools/useToolRunner.ts` | Use the outcome interpreter in both tool-execution paths instead of labeling every non-error response `Completed`. | Full frontend suite passes. |
| `apps/web/src/features/chat/components/ToolApprovalPanel.tsx` | Added an amber blocked/needs-user-attention state so YouTube autoplay/consent blocks are not shown as green completion. | Frontend type check and production build pass. |
| `docs/HINAA_YOUTUBE_PLAYBACK_CONTRACT_2026-08-13.md` | Recorded one-tab ownership, player-state acceptance, autoplay recovery, and source-backed browser limitations. | Contract review and release evidence recorded. |

The supplied UI failure is mechanically addressed, but real playback remains **PENDING_USER_RUNTIME** because YouTube, account/consent pages, advertisements, and Chrome autoplay policy require a real local browser observation. HINAA now reports the blocked state honestly rather than claiming sound is playing.


## Phase 24 — Automation and image-workflow reliability

| Surface | Change | Verification |
|---|---|---|
| Shared tool dispatcher | Resolved postponed Python type annotations with `get_type_hints()` before Pydantic construction. This fixes the observed `youtube_playback_request` 502: the prior dispatcher passed a raw dict to a future-annotated Pydantic handler. | Transport-level API regression reproduces the prior future-annotation scenario and receives the typed model successfully. |
| Verified YouTube path | The existing owned-tab media verification repair can now reach its browser code instead of crashing at parameter dispatch. | YouTube helper and dispatcher regressions pass; actual Windows browser playback remains user-runtime evidence. |
| Local ComfyUI generation | `image_generate` now checks the local renderer before persisting an image set. An offline service returns `COMFYUI_UNAVAILABLE` and the exact local recovery path rather than creating doomed pending slots. | Offline provider regression passes without a DB write or remote request. |
| You.com public image search | Added explicit confirmation-gated `image_search`, normalized bounded public image/source links, intent routing for `search/find images`, and a chat gallery. The provider's documented beta/early-access 403 becomes an actionable access message. | Mocked image client covers query, URL safety, normalized cards, access denial, and tool confirmation. |

The You.com Images endpoint is documented as beta, unmaintained, and early-access-only. HINAA labels it accordingly; it is not substituted for private local ComfyUI generation and must not be represented as universally available.[8]

[8]: https://you.com/docs/api-reference/images/images "You.com Images API Reference"


| Tool-language truthfulness | Updated the immutable tool policy after the supplied screenshot showed HINAA saying a song was playing before its approved action returned. Planned actions now use future-facing language; completed language is reserved for verified returned tool events. Image status examples now use Devanagari Hindi plus English technical terms. | Prompt-assembly and conversation-brain regressions pass. |

## Phase 25 — Fullscreen live companion polish
| Surface | Change | Verification |
|---|---|---|
| Existing single avatar stage | Extended `AvatarPresence` rather than adding a second canvas. The stage now renders a professional fullscreen overlay with recent turns, live partial transcription, streamed assistant text, truthful status chips, input meter, and explicit start/stop/pause/resume controls. | `FullscreenCompanionOverlay` UI regressions cover microphone controls, transcript states, and unavailable-device recovery. |
| Fullscreen entry | Native browser fullscreen remains preferred. An immediate in-page theater fallback now expands the same stage to the viewport if browser policy or an embedded context rejects the Fullscreen API. | TypeScript and production build pass. Initial active-browser inspection showed the previous fullscreen control did not visibly enter native fullscreen; post-repair user-browser refresh was blocked by a temporary browser-extension timeout, so final visual evidence must be repeated locally. |
| Visual system | Added responsive Ink Rose stage chrome, high-contrast transcript cards, voice dock, active microphone meter, keyboard-visible control focus, and reduced-motion fallbacks. | Complete frontend suite passes: 30 files, 127 passing tests, 2 existing todos; TypeScript and Vite/PWA build pass. |

## Phase 26 — Mobile and local-workflow hardening
| Surface | Change | Verification |
|---|---|---|
| Responsive companion layout | Updated phone portrait framing through the existing anatomy-aware avatar camera, enlarged stage controls, and converted the mobile welcome scene to a compact two-by-two action grid so Voice remains visible above the composer. | Chromium checks at 393×851 and 320×568 pass for no overflow, stage/composer visibility, no console errors, and all four primary welcome actions inside the viewport. |
| Repeatable mobile gate | Repaired `check:mobile` to use the installed Chromium executable rather than requiring a separately downloaded Playwright browser. The check now verifies Research, Create, Continue work, and Talk to HINAA individually. | `pnpm check:mobile` passes on both supported phone viewports. |
| Local ComfyUI recovery | Preserved terminal `COMFYUI_UNAVAILABLE` results at the shared tool dispatcher and taught Image Studio to read direct or legacy nested results. No image poll begins if the local renderer cannot create a job. | API dispatcher/image tests and Image Studio regressions pass. |
| Web-search transparency | The chat source panel now presents the backend’s provider-route notice, so a public fallback is not visually confused with a configured private You.com search. | Focused renderer regression passes. |

## Phase 27 — Truthful research workflow and mobile context workspace
| Surface | Change | Verification |
|---|---|---|
| Research progress | Removed the unrelated Lightswind source-convergence animation from HINAA’s context workspace. Reused the existing `ActivityPanel` and the established agent-step state instead, so progress names actual planning, approval, and synthesis stages. | Context workspace regression verifies real stages render and Lightswind/YouTube graphics do not. |
| Trustworthy workflow copy | Planning now explicitly says no pages have been fetched and that live research starts only after the user approves the proposed external action. | Type checking and focused workspace tests pass. |
| Mobile workspace | Corrected the context drawer’s fixed-width inner shell so it cannot overflow a narrow fullscreen mobile drawer; aligned workspace contrast and controls to Ink Rose. | Phone layout checks pass at 393×851 and 320×568. |
| Provider recovery | Web-search provider errors with an empty source list now render a named research-service recovery panel, including the normalized code and a bounded next step. | Focused chat renderer regression passes. |
