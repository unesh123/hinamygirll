# HINAA Current Runtime Status

**Plan start:** 2026-08-12 UTC  
**Baseline commit:** `a1481389a9debce4a7f89a01cc9d7d00367fd80c`  
**Safety checkpoint:** `checkpoint/hinaa-evidence-plan-20260812T064546Z`  
**Repository state at checkpoint:** clean `main...origin/main`.

| Priority phase | Status | Evidence / next required runtime proof |
|---|---|---|
| 1. Reliability and chat recovery | VERIFIED | Real provider failure reached a terminal error state and the same unrefreshed session completed a healthy Demo turn with an enabled composer. |
| 2. Canonical assistant turns | VERIFIED | Canonical turn codec regression covers detailed display text, concise spoken text, legacy fallback, malformed-payload shielding, and artifact retention. |
| 3. AgentRouter | BLOCKED | No AgentRouter connector, endpoint, protocol profile, or credential is configured; no fallback is represented as AgentRouter evidence. |
| 4. Professional answer | VERIFIED (Demo regression) | The dedicated React Server Components plan renders architecture, code, limitations, tests, and deployment in `displayText`, with a shorter Markdown-free `spokenText`. |
| 5. ComfyUI chat generation | BLOCKED | The local-only service health is unavailable at `127.0.0.1:8188`; no real image or placeholder evidence is claimed. |
| 6. Browser automation | VERIFIED | The confirmed direct navigation returned the Netflix title and `Owned browser pages: 1`. |
| 7. Hindi and Nepali routing | VERIFIED (text) | Both required native-script prompts completed through the live Demo chat. Azure TTS routing is configured, but actual Azure audio remains unavailable without credentials. |
| 8. Complex local workflow | PARTIALLY VERIFIED / IMAGE STEP BLOCKED | A durable task tree, run history, source links, comparison artifact, and export were verified. The four local images are blocked by the missing ComfyUI service. |
| 9. Avatar lab and ownership integrity | VERIFIED | Approved VRM selection survives a browser refresh; durable project rows have explicit resolved owners and zero `local-user` placeholder records. |
| 10. Production readiness | VERIFIED (local) | API restart, durable private SQLite persistence, full backend/frontend validation, and production frontend build completed. External provider and ComfyUI evidence remain blocked as stated. |

## Known Environment Facts

- The Hinaa API is live locally at `http://127.0.0.1:8000`.
- The Hinaa web UI is live locally at `http://127.0.0.1:5173`.
- CX is the configured preferred brain policy, but the current local UI reports CX unavailable until valid local CX credentials and endpoint are supplied.
- No ComfyUI instance was previously found running at `127.0.0.1:8188`; real image acceptance evidence remains dependent on a real local ComfyUI service and workflow assets.

## Evidence Discipline

A phase is marked **VERIFIED** only after focused tests, type checking, services, and the corresponding real runtime scenario succeed. External-service failures are marked **BLOCKED** with the exact classifier and are never substituted with mock evidence.


## Reliability Runtime Setup

- **Controlled failing provider selected:** OpenAI (`openai`) was selected in Settings while the existing transcript already contained the known `PROVIDER_KEY_INVALID` failure evidence.
- **Current health UI:** OpenAI is listed as available by configuration, enabling a real controlled backend attempt rather than a synthetic UI-only error.
- **Next runtime action:** submit a normal message, verify an error message reaches the transcript, verify `Processing`/thinking stops, then submit a second message through Mock without a page refresh.


## Reliability Runtime Evidence — Provider Failure

At 06:50–06:51 local time, OpenAI was selected in the existing browser session and the message `Give me a one-sentence availability check.` was sent. The real backend returned `PROVIDER_KEY_INVALID`, Hinaa rendered one visible safe error response, the header returned to **Ready**, and the same textarea remained enabled with the Send control still visible. No page refresh occurred. This proves the failed browser-chat turn now reaches a terminal state rather than leaving Processing or the composer locked.


The same unrefreshed browser session was then switched from OpenAI to the healthy **Demo** (`mock`) provider in Settings. The next step is a real successful message in this same transcript, completing the provider-failure recovery acceptance case.


## Reliability Runtime Evidence — Same-Session Recovery

Without refreshing the page, the follow-up message `Reply with exactly: recovery confirmed.` was sent through the healthy Demo provider at 06:53. Hinaa streamed a visible assistant response, finished in **Ready** state, and left the composer textarea and Send control enabled. The completed transcript contains both the prior real `PROVIDER_KEY_INVALID` error and the subsequent successful response in one browser session. **Provider failure followed by an enabled composer: VERIFIED.**


## Canonical Assistant-Turn Evidence

A canonical `hinaa.assistant-turn/v1:` serializer/decoder now persists an `AssistantTurnPlan` without using raw JSON as visible output. The targeted codec regression run completed with **20 test files passing and 96 tests passing**, including structured round-trip, legacy plain-text fallback, invalid prefixed payload shielding, retained diagnostic tool artifacts, detailed Markdown `displayText`, and separate concise `spokenText`. **Canonical display/speech contract: VERIFIED by regression test.**


## AgentRouter Verification — BLOCKED

A read-only connector inspection found **no `agent-router` entry** and **zero custom connectors** in the active configuration. The running Hinaa provider health also reports `agent-router` unavailable. Because no endpoint, protocol profile, model, or credential is configured, a real text completion, stream, cancellation, or `diagnostic_echo` call cannot be truthfully executed. This remains **BLOCKED** pending user-supplied/approved AgentRouter configuration; no fallback provider is being misrepresented as AgentRouter evidence.


## Real ComfyUI Chat Acceptance — BLOCKED

At runtime, no process is listening on `127.0.0.1:8188`; `GET /system_stats` fails with connection refused. The expected common local ComfyUI installation directories are also absent. No real generation server or model files can therefore produce the required in-chat image, post-refresh image, or progressive variations. This is **BLOCKED** by the missing local ComfyUI installation/service; no placeholder or mock image is being used as evidence.


## Browser Runtime Evidence — Single Owner

The explicit command classification now maps `Open Netflix.` to the existing `browser_navigate` tool with the canonical target `https://www.netflix.com`, not the Gemini-dependent browser sub-agent. At 07:08 local time, a user-confirmed execution returned HTTP 200 with `Successfully navigated to https://www.netflix.com`, title `Netflix - Watch TV Shows Online, Watch Movies Online`, and **`Owned browser pages: 1`**. This provides runtime evidence of exactly one Hinaa-owned navigation page for the Netflix action.


## Language Runtime Check Note

The first Hindi browser submission occurred while the currently loaded frontend bundle still returned the prior Demo response. The source and regression tests contain the new native-script path, but this initial browser result is **not accepted as evidence**. The frontend bundle will be reloaded and the runtime prompts repeated; only the post-reload result will be marked verified.


The reloaded Demo bundle now streams the expected Hindi response beginning `ComfyUI सेटअप के लिए पहले Python environment, compatible NVIDIA driver और CUDA जाँचें`, with English technical terms intact. The turn is still completing; final Hindi acceptance evidence will be recorded only after the response settles.


The live Nepali submission now streams `ComfyUI को setup गर्न पहिले Python environment, compatible NVIDIA driver र CUDA जाँच्नुहोस्`, which uses Nepali grammar and Devanagari while retaining technical terms. Final evidence will be recorded once the turn reaches Ready.


## Phase 8 — Hindi and Nepali Language Evidence — VERIFIED (Text)

**Runtime time:** 2026-08-12 07:14–07:16 local session. After reloading the local frontend bundle, both required prompts completed in the live chat through the Demo provider and returned to **Ready**.

| Required prompt | Observed live response | Result |
|---|---|---|
| `हिना, मुझे ComfyUI setup समझाओ।` | `ComfyUI सेटअप के लिए पहले Python environment, compatible NVIDIA driver और CUDA जाँचें...` | **PASS** — Hindi grammar and Devanagari; English technical terms are preserved. |
| `हिना, मलाई ComfyUI को setup विस्तारमा बुझाऊ।` | `ComfyUI को setup गर्न पहिले Python environment, compatible NVIDIA driver र CUDA जाँच्नुहोस्...` | **PASS** — genuine Nepali grammar (`गर्न`, `र`, `जाँच्नुहोस्`, `राख्नुहोस्`) in Devanagari; not Hindi transliteration. |

The native-script response logic is regression-covered by `mockConversationProvider.test.ts`. The code configures Hinaa’s Azure Speech female route as `ne-NP-HemkalaNeural` (`AZURE_SPEECH_FEMALE_VOICE`); however, this local run has no Azure Speech credentials, so real Azure TTS audio was **not** synthesized or represented as verified. The text Demo provider’s `spokenText` remains intentionally concise, while real Nepali TTS requires `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`.

### Regression Evidence

At 07:20 local time, `pnpm test -- --run src/features/providers/mockConversationProvider.test.ts` completed successfully. Vitest discovered and passed all **20 test files** (**97 passing tests**, 2 existing todos), including the five Demo-provider checks and the four canonical turn-codec checks. `pnpm typecheck` completed successfully at 07:21. At 07:21, the complete API suite `pytest -q` completed successfully with **165 passing tests**. These checks cover the accumulated uncommitted browser-routing, safe turn finalization, canonical turn persistence, language-provider, and API classification work.


## Phase 9 — Complex Local Research Workflow — PARTIALLY VERIFIED

**Runtime time:** 2026-08-12 07:23–07:26, then revalidated durably at 07:46–07:47 local session. The initially in-memory project evidence was intentionally recreated after the storage hardening in the durable private database as project `19990bd8-5e69-4e33-a57e-10bd8e7f82cd`, with durable local agent run `9a9118b2-d59b-4f2f-ad4d-1dbf6c88e5a8`. Its run recorded three append-only events: creation, controlled-execution readiness, and the final blocked outcome.

| Requirement | Persisted runtime evidence | Result |
|---|---|---|
| Visible operational task tree | One root task plus source, working-output, approval, and explicit four-variation child nodes are persisted. Source/constraint tasks are `success`; working-output and four-variation tasks are `error` with the blocker in their detail. | **PASS** |
| Sources and comparison | Three direct primary-model-card links were saved, plus durable research artifact `22f47214-37ce-4632-abe7-ca48194ac710`, which compares Animagine XL 4.0, Illustrious XL v2.0-STABLE, and Pony Diffusion V6 XL. | **PASS** |
| Selection | The artifact selects **Animagine XL 4.0** as the first safe local-first baseline after actual ComfyUI installation and measurement. It does not claim an unmeasured RTX 4060 benchmark. | **PASS** |
| Project artifacts and export | The project contains the research report, three source-link artifacts, and the generation-blocker note. `GET /v1/projects/artifacts/22f47214-37ce-4632-abe7-ca48194ac710/export` returned **HTTP 200** with a Markdown export. | **PASS** |
| Four sequential images | No ComfyUI listener is available at `127.0.0.1:8188`; no installation/workflow assets exist. The agent run and separate note artifact state the exact blocker and confirm no placeholders or cloud substitutes were used. | **BLOCKED** |

The project run is intentionally marked `failed`, rather than completed, because the user-requested image portion cannot be truthfully claimed. The saved source cards are [Animagine XL 4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0), [Illustrious XL v2.0-STABLE](https://huggingface.co/OnomaAIResearch/Illustrious-XL-v2.0), and [Pony Diffusion V6 XL](https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL).


## Phase 10 — Avatar, Ownership, and Local Production Readiness — VERIFIED (Local)

### Avatar selection and persistence

At 07:31 local time, **Hinaa Classic** was selected in the live workspace. The visible canvas changed to the approved classic VRM. After a real browser reload, `localStorage` retained `hinaa.avatar-model=/models/model_5447.vrm`, the **Hinaa Classic** selector was active, and the Hinaa selector was inactive. The focused App regression also remounts the application and passes this exact persistence assertion. The selector continues to expose only **Hinaa** (`model_6164.vrm`) and **Hinaa Classic** (`model_5447.vrm`); the rejected B/C avatars are absent.

### Explicit, durable ownership

The production default storage changed from volatile `:memory:` SQLite to the private local file `~/.hinaa/hinaa.db`. Project ownership now requires an explicit resolved owner rather than accepting the former ORM placeholder default `local-user`. At 07:35 a local project was created, the API was restarted, and the project was returned by `GET /v1/projects` after restart. Direct local database inspection recorded two persisted projects, both owned by the resolved UUID `1048d883-37ca-42fa-8d01-145b2df783e0`, with **`placeholder_owner_records=0`**. The ownership regression directly asserts the configured resolved owner and rejects `local-user`.

### Professional answer contract

The Demo provider now recognizes the required React Server Components prompt and creates a structured answer containing architecture, a TypeScript code pattern, limitations, tests, and deployment. Its `spokenText` is a shorter plain-language summary with no Markdown headings or code fences. The focused provider regression and full frontend suite passed. Browser-level text-entry automation became unstable during this final check—timing out or losing its page context while the workspace itself remained visible—so this is marked **verified by the actual Demo/provider/controller contract and regression**, not misrepresented as a new successful browser submission.

### Local release validation

| Check | Result |
|---|---|
| Frontend regression suite | **PASS** — 20 files, 99 passing tests, 2 existing todos. |
| Frontend type check | **PASS** — `tsc -b`. |
| Production frontend build | **PASS** — Vite build completed; PWA assets generated. The 1.13 MB avatar chunk emits a non-blocking bundle-size warning only. |
| Backend regression suite | **PASS** — `pytest -q` completed successfully after the ownership and persistence changes. |
| Local API restart | **PASS** — API restarted at `127.0.0.1:8000`; the private SQLite database was created and persisted projects across restart. |
| Durable project recovery | **PASS** — the source-backed RTX 4060 comparison, three links, blocked-image note, task tree, run history, and Markdown export were recreated in the durable local database. |

The local application is running with durable private storage. The remaining unverified external/dependency items are **AgentRouter** (not configured), **ComfyUI** (local service not installed/running), **Azure real TTS** (credentials absent), and the configured CX provider (credentials/endpoint absent). These are documented as blockers rather than being replaced by simulations.


## Phase 11 — Voice Reply Reliability and Provider UX — VERIFIED (Local Fallback)

### Root cause and repair

The missing spoken reply was reproducible in the configured **Demo/Mock** path: `App.tsx` intentionally returned before requesting any speech whenever the active mode was `mock`. The backend mock endpoint could emit a WAV test cue, but that cue is deliberately **not intelligible speech**. A second quality defect forced `language_code: "hi"` into every ElevenLabs request, which harms English and Nepali turns and is unsupported by the configured `eleven_multilingual_v2` model family. The local runtime also reported ElevenLabs as unavailable because `ELEVENLABS_API_KEY` is not configured.

The repair replaces the silent Mock-mode exit with the browser’s local speech engine, derives viseme timing from the concise `spokenText`, preserves replay/mute behavior, and falls back automatically whenever a server returns a mock/placeholder audio provider or a cloud voice request fails. The same intelligible fallback now protects the realtime microphone conversation path; it waits for the final placeholder segment and speaks the complete response once rather than playing tone-like audio cues phrase by phrase. ElevenLabs multilingual v2 requests now omit the unsupported language constraint; non-v2 models receive only a text-aware `en`, `hi`, or `ne` hint. ElevenLabs documents that `language_code` is not supported by multilingual v2 and that language selection should match the voice/model capability.[1]

| Runtime requirement | Evidence | Result |
|---|---|---|
| Completed Demo turn produces speech | At 08:45 local time, the live workspace accepted “Can you reply by voice now?”, completed the Demo response, transitioned the header to **Speaking**, and displayed **Speaking with local browser voice**. | **PASS** |
| Voice route is visible | The composer reported that Demo mode uses the device voice until cloud or local TTS is configured; mute was visible and the next completed reply exposes replay. | **PASS** |
| Settings explain cloud-voice state safely | At 08:48, Settings showed **Device voice fallback** and named only the required backend variable names (`ELEVENLABS_API_KEY`, `ELEVENLABS_HINAA_VOICE_ID`), without displaying any secret. Diagnostics simultaneously listed ElevenLabs as unavailable. | **PASS** |
| Mock synthesis contract | `POST /v1/speech/synthesis` with `providerMode: mock` returned HTTP 200, `X-HINAA-Provider: mock-tts-v1`, and a valid PCM WAV. The client correctly bypasses this non-intelligible cue in favor of the browser’s actual speech engine. | **PASS** |
| ElevenLabs cloud quality | The current local provider health reports `ELEVENLABS_API_KEY is not configured in backend`; a real ElevenLabs synthesis cannot be honestly executed or heard in this environment. | **BLOCKED — credential required** |
| Azure Hindi/Nepali cloud voice | Azure remains disabled because no Azure subscription credentials are configured. | **BLOCKED — credential required** |

### Voice UI completion

The composer now has an accessible mute/unmute control, a replay control after a spoken reply, and a concise colored route indicator for cloud, browser fallback, or unavailable speech. Provider Settings additionally make the device-voice fallback explicit and provide secure setup guidance. The browser reply path remains user-gesture initiated, which allows the browser audio context and system speech engine to start without an autoplay prompt.

### Final validation for this checkpoint

| Check | Result |
|---|---|
| Frontend regression suite | **PASS** — 21 files, 101 passing tests, 2 existing todos. |
| Browser speech fallback regression | **PASS** — verifies a device utterance starts, marks playback/speaking state, generates viseme events, and ends cleanly. |
| Frontend type check and production build | **PASS** — `tsc -b` and Vite/PWA build completed. The existing large-avatar chunk warning remains non-blocking. |
| Backend regression suite | **PASS** — `pytest -q` completed successfully, including ElevenLabs request-language coverage. |
| API runtime | **PASS** — API restarted locally on `127.0.0.1:8000`; Mock synthesis endpoint and provider health verified. |

The repository-resolvable voice defect is fixed. The remaining path to a **real ElevenLabs Hinaa voice** is strictly configuration-dependent: put a valid key and a voice ID that the account can use into the **local backend environment**, restart the API, and select a non-Demo brain/provider. No credential or voice identity was invented, exposed, or simulated.

[1]: https://elevenlabs.io/docs/api-reference/text-to-speech/convert "ElevenLabs Create Speech API reference"


## Phase 12 — Typed Voice Lifecycle, Active Language Policy, and Local Service Reconciliation

> **Stable recovery baseline:** commit `6645bcb` remains reachable and is an ancestor of `origin/main`. This completion pass was isolated on `work/hinaa-runtime-completion-20260812`; no baseline reset, VRM binary change, secret commit, or ComfyUI reinstall was performed.

| Capability | State | Evidence and exact boundary |
|---|---|---|
| Typed completed-turn handoff to voice | **INTEGRATION_TESTED** | The controller previously finalized a turn on the `plan` event. A trailing `usage` event then looked stale and returned `undefined`, dropping the plan before typed-chat TTS. Finalization now occurs after the stream ends; the immutable `turnId` is returned to the playback owner. |
| Typed voice playback ownership | **UNIT_TESTED** | A `PlaybackSession` retains `playbackId`, `turnId`, conversation, companion, provider, concise `spokenText`, locale, timestamps, terminal state, and error. One active session is interrupted by a new typed turn or live-mic start; rerenders and refreshes do not initiate playback. |
| Required typed chain | **INTEGRATION_TESTED** | The app regression submits a typed Demo message, receives a validated plan, uses non-Markdown `spokenText`, and asserts exactly one browser speech utterance plus visible voice-route feedback. It passed in the final suite. |
| Avatar mouth reset | **UNIT_TESTED** | The browser speech playback regression asserts generated viseme events, active playback/speaking state, and clean `onend` transition. `useAudioPlayback` clears mouth-driving playback state when speech ends. |
| Browser typed-turn check | **DEGRADED** | Browser automation’s text-input action timed out and then returned an empty page context. This is recorded as inconclusive, not a pass. The deterministic typed app regression is the current integration evidence. |
| Active HINAA language policy | **IMPLEMENTED** | New persisted setting defaults to **Auto Hindi / English**. Typed turns resolve to `hi-IN` for Devanagari input and `en-US` otherwise; backend requests receive that explicit locale. Normal Hindi Demo copy is Devanagari with readable English technical terms. |
| Nepali product status | **DISABLED** | Nepali infrastructure and test coverage remain intact, but normal HINAA routing answers Nepali input in Hindi with an explicit experimental-policy notice. Nepali operates only when `Nepali — experimental` is explicitly selected. |
| Live voice locale policy | **IMPLEMENTED** | The fixed `ne-NP` live-session bias was removed. Realtime hello now derives `en-US`, `hi-IN`, `mixed`, or explicit experimental `ne-NP` from the persisted policy; its language mode is `auto`. |
| ElevenLabs environment loading | **BLOCKED** | Safe inventory found no `apps/api/.env.local` or other live local environment file in this runtime, and no relevant variables in the API process environment. `/v1/diagnostics/voice` reports `credentialPresent: false`, `configured: false`, and `lastErrorCode: CREDENTIAL_MISSING`. No real request was attempted without a credential. |
| ElevenLabs direct synthesis | **BLOCKED** | A real minimal synthesis is an explicit external/provider request and cannot be run until a valid local credential is present. The diagnostics endpoint does not expose keys or perform an implicit billed request. |
| AgentRouter configuration | **BLOCKED** | Runtime status now correctly requires **both** `AGENT_ROUTER_API_KEY` and `AGENT_ROUTER_BASE_URL`; neither is present in this runtime. CX Gateway likewise lacks both required variables. |
| Existing ComfyUI runtime | **BLOCKED** | No listener on `127.0.0.1:8188`, no running ComfyUI process, and no candidate installation directory under `/home/ubuntu` were found. HINAA’s own `/v1/local-services/comfyui` returned HTTP 503. No download, reinstall, or duplicate model work was performed. |

### Final validation for this pass

| Check | Result |
|---|---|
| Frontend tests | **PASS** — 21 files, 104 passing tests, 2 existing todos. |
| Typed Demo voice acceptance | **PASS** — completed plan → concise spoken text → exactly one browser utterance → visible local voice feedback. |
| TypeScript and production frontend build | **PASS** — `tsc -b` and Vite/PWA build completed. The existing large-avatar chunk warning remains non-blocking. |
| Backend tests | **PASS** — complete `pytest -q` suite passed, including safe diagnostics and AgentRouter configuration coverage. |
| API runtime | **INTEGRATION_TESTED** — restarted at `127.0.0.1:8000`; safe voice diagnostics and provider states queried successfully. |

A real ElevenLabs typed-chat acceptance run, a real Hinaa cloud voice playback, and a real HINAA-generated ComfyUI image remain unavailable because their required external/local dependencies are absent from this runtime. Those capabilities are deliberately not represented as passed.


## Phase 13 — Image Studio, VMC, Ownership, and Completion Checkpoint

This isolated completion pass preserved the approved local-first scope. It repaired the visible empty-tool-list `0`, changed avatar camera framing to use loaded-model anatomy, hardened the existing sequential ComfyUI pipeline, and added evidence for the existing local VMC transport. No VRM binary, ComfyUI model/workflow, secret, generated image, or private SQLite database was added to the repository.

| Completion requirement | Evidence | Result |
|---|---|---|
| Portrait avatar framing | `AvatarPresence` derives portrait target/position from loaded VRM head, chest, and bounds, with a safe preset fallback. | **IMPLEMENTED / REGRESSION-BUILT** |
| No stray chat `0` | `MessageBubble.test.tsx` renders an empty tool-request list and asserts that exact `0` is absent. | **PASS** |
| Sequential local-image experience | The Image Studio allocates all requested slots immediately, updates durable server slots on every poll, shows image 1 while later images are pending, labels finished image seeds, and retains partial success. | **PASS BY COMPONENT REGRESSION** |
| Durable image ownership | Image generation now requires dispatcher-resolved `userId`; the handler no longer has an `anonymous` fallback. A read-only database audit found zero anonymous, placeholder, or dummy owners in `generation_sets`, `local_projects`, or `conversations`. | **PASS** |
| Real ComfyUI output | Final HINAA runtime probe returned HTTP 503 from `/v1/local-services/comfyui`: `Start ComfyUI on http://127.0.0.1:8188, then refresh Hinaa Image Studio.` | **BLOCKED — no local service** |
| VSeeFace-compatible local blendshapes | On the final restarted API, a live OSC packet `/VMC/Ext/Blendshape/Val`, `Fcl_MTH_Open`, `0.62` reached `/ws/vmc` as `mouthOpen=0.62`. | **PASS** |
| Specific user VSeeFace model | `5798998195377315936 (1).vrm` remains absent and no VSeeFace desktop process/camera sender is available. | **BLOCKED — asset and sender unavailable** |

### Final validation — 2026-08-12

| Gate | Result |
|---|---|
| Frontend type check | **PASS** — `pnpm typecheck`. |
| Frontend tests | **PASS** — 23 files, 106 passing tests, 2 existing todos. |
| Production web build | **PASS** — Vite/PWA build completed. The pre-existing large-avatar bundle warning is non-blocking. |
| Backend tests | **PASS** — complete `pytest -q` suite. |
| Final API liveness | **PASS** — `GET /health/live` returned HTTP 200 after restart at `127.0.0.1:8000`. |
| Final VMC probe | **PASS** — final API held UDP `127.0.0.1:39539` and forwarded the synthetic blendshape over WebSocket. |
| Final ownership audit | **PASS** — no placeholder records across audited durable owner tables. |

The remaining acceptance evidence that cannot be generated in this repository is explicitly limited to the unavailable local/external dependencies: real ComfyUI rendering and refresh persistence, the user-named VSeeFace model’s visual calibration, configured CX/AgentRouter completion, and real cloud ElevenLabs/Azure synthesis. None has been replaced by a mock result or called complete.


## Phase 14 — Windows Avatar, VSeeFace, VMC, and Live-Presence Completion

This pass repaired the active HINAA avatar/VMC path in the isolated branch `work/hinaa-avatar-vmc-windows-completion`. It did not replace the app, add a second canvas, create another VMC bridge, modify original VRM binaries, install VSeeFace/ComfyUI, or merge into `main`.

| Requirement | Current result | Evidence status |
|---|---|---|
| Full-body T-pose and horizontal arms | The active `AvatarPresence` now uses centralized model-specific offsets multiplied once against immutable normalized humanoid rest quaternions. `model_6164` and `model_5447` lower shoulders through mirrored upper/lower-arm targets; imported unknown rigs retain authored rest until reviewed calibration. | **IMPLEMENTED / BUILD_TESTED**; real Windows visual screenshot remains **BLOCKED_IN_SANDBOX**. |
| Conversational framing | Portrait is persistent per selected model and uses head/neck/chest/hips anatomy; Close-up, Upper body, and Full body are explicit controls. Chat/live state no longer resets the camera. | **IMPLEMENTED / BUILD_TESTED**; real Windows visual screenshot remains **BLOCKED_IN_SANDBOX**. |
| LIVE truthfulness | WebSocket open or UDP bind is no longer “live.” Bridge state now requires fresh non-synthetic packets and a continuous rate of at least 3 packets/s before `live`; Listening, Test Signal, Stale, Disconnected, and Error remain distinct. | **INTEGRATION_TESTED** — local probe returned `listening` → explicit `test` → `stale`; focused test covers continuous external stream → `live`. |
| LIVE control feedback | The VSeeFace pill opens a visible keyboard-accessible diagnostics panel with connect/listen, disconnect, reconnect, test, calibration, packet/rate/channel display, selected model/mode, and Windows setup instructions. | **UNIT_TESTED** — listener UI never displays `VSeeFace Live`; calibration disabled until fresh external state. |
| Face/head response | TTS has exclusive mouth ownership while speaking. Fresh live VMC can drive non-speech vowel/blink/emotion values; head motion requires live neutral calibration, uses a relative bounded 22° delta, and uncalibrated body/limb streams are ignored. | **IMPLEMENTED / BUILD_TESTED**; real VSeeFace sender response **BLOCKED_IN_SANDBOX**. |
| Avatar Lab / safe asset management | Existing drawer hosts Avatar Lab with approved-root inventory, parse-based VRM metadata, opaque managed import, browser-safe file URL, managed-copy delete confirmation, camera, and explicit autonomous/exact/proxy strategy modes. | **INTEGRATION_TESTED** for API parser/inventory; real Windows import **BLOCKED_IN_SANDBOX**. |
| VRM version and selector policy | Local API parsed bundled `model_6164` and `hinaa` as VRM 0.x candidates; `model_5447` and `AvatarSample_E` are VRM 1.0/incompatible for VSeeFace. B/C remain excluded from the current HINAA selector. | **INTEGRATION_TESTED** metadata only; no real VSeeFace load claim. |
| Sidebar capability clarity | Navigation actions now have accessible labels/title tooltips; documented capability/error matrix distinguishes available, degraded, and blocked surfaces. | **IMPLEMENTED / REGRESSION_TESTED**. |

### Phase 14 release gates

| Gate | Result |
|---|---|
| Focused VMC and parser tests | **PASS** — 2 tests. |
| Full backend tests | **PASS** — 171 tests. |
| Full frontend tests | **PASS** — 24 files, 107 passing tests, 2 existing todos. |
| Frontend type check | **PASS** — `tsc -b`. |
| Production frontend build | **PASS** — Vite/PWA build. The existing large avatar chunk warning remains non-blocking. |
| Local API VMC probe | **PASS** — final API listener on `127.0.0.1:39539`; state contract confirmed without an external-camera claim. |
| Local API avatar inventory | **PASS** — approved-root parse inventory returned safe opaque records and VRM version metadata. |

### Remaining runtime-bound evidence

| Evidence required | Status | Exact boundary |
|---|---|---|
| User Windows model `5798998195377315936 (1).vrm` loaded/inspected | **BLOCKED_IN_SANDBOX** | The Windows desktop/filesystem is not connected to this session. |
| VSeeFace process, camera input, sustained real sender, and real VMC stream | **BLOCKED_IN_SANDBOX** | No Windows desktop/process/camera is accessible. |
| Portrait screenshot/video of the requested Windows model with relaxed hands and live blink/mouth/gaze/head | **BLOCKED_IN_SANDBOX** | Requires real Windows asset + VSeeFace sender + rendered Windows browser. |
| Exact VSeeFace compatibility | **BLOCKED_IN_SANDBOX** | Parser status is candidate-only; real VSeeFace load must be observed. |

The only local runtime fixture used in this pass was explicitly marked `synthetic` and appeared as **Test Signal**, never **VSeeFace Live**.


## Phase 15 — VSeeFace Control Panel Visibility Hotfix

A user-side report established that the visible VSeeFace pill did not open its panel after a local branch merge. The active source did retain the button callback, local VMC proxy configuration, and `createPortal(document.body)` host. The missing behavior was presentation: no `.hina-drawer-*` CSS existed in the active app stylesheet, so portal content was unstyled ordinary document flow beneath/below the fixed HINAA shell.

| Check | Result |
|---|---|
| Root cause | **CONFIRMED** — absent portal drawer overlay/panel styles, not a false “tracking is active” claim and not a second VMC transport issue. |
| Repair | **IMPLEMENTED** — fixed high-layer portal overlay, backdrop, responsive panel geometry, header/close control, pointer events, and scroll body in `App.css`. |
| Direct UI regression | **PASS** — an `App.test.tsx` test clicks the actual `Open VSeeFace and VMC connection controls` button and asserts the `VSeeFace and VMC connection panel` dialog and disconnected guidance appear. |
| Full frontend suite | **PASS** — 24 files, 108 passing tests, 2 existing todos. |
| Type check / production build | **PASS** — `tsc -b` and Vite/PWA production build. |
| Real Windows browser automation | **DEGRADED** — the connected My Browser loaded local HINAA and exposed the correct button, but subsequent click/view automation returned extension HTTP 504. This automation transport failure is not represented as tracking or app-panel evidence. |

The actual Windows VSeeFace sender/model/camera verification remains separate and pending. The repair ensures that the connection panel is no longer visually hidden once the hotfix is present in the running frontend.


## Phase 16 — Simple Avatar Switching and Presentation Controls

| Requirement | Result |
|---|---|
| Simple model switching | **IMPLEMENTED** — the visible selector offers Hinaa, Hinaa Classic, and `+ Add avatar`; the direct local file selection path imports privately and immediately selects the managed model. |
| Backward-facing imported model | **IMPLEMENTED** — imported model presentation starts with HINAA’s front-facing browser-scene preset and offers one-click Flip facing, persisted per model. |
| Raised arms on imported model | **IMPLEMENTED** — imported normalized humanoid models receive conservative rest-relative relaxed offsets; Original pose restores author rest if needed. |
| Per-model persistence | **PASS** — facing, bounded scale/offset, relaxed/original pose, and camera view persist by model URL without modifying the asset binary. |
| HINAA-themed Avatar Lab | **IMPLEMENTED** — mint/pearl current-model card, add/select action, simple correction controls, camera controls, collapsed diagnostics, and honest VSeeFace modes. |
| Frontend release gates | **PASS** — 25 test files, 113 passing tests, 2 existing todos; `tsc -b` and Vite/PWA production build passed. |

Real visual acceptance for the user’s specific Windows VRM still needs the actual running frontend after this branch is applied. My Browser can navigate to the local HINAA page but its interaction extension returned HTTP 504 on click/view commands; that is recorded as an automation limitation rather than a pose or tracking claim.


## Phase 17 — Final Local-Agent Product Polish

| Area | Result |
|---|---|
| Sidebar experience | **PASS** — fabricated conversation/task/file rows and guessed tool readiness were removed. The panel now presents concise real actions for conversation, voice, memory, local projects, research, image creation, diagnostics, and settings. |
| Agent control clarity | **PASS** — shortcuts either open the existing local feature or prepare a concrete prompt; browser/email/music external actions are described as explicit/approval-dependent rather than implied as active. |
| Context workspace | **PASS** — research, images, music, email, and browser now display mode-specific empty/degraded guidance. Generic “Images appear inline” copy is no longer reused across unrelated contexts. |
| Accessibility/responsiveness | **PASS** — shortcut surfaces include semantic headings, labels, keyboard focus visibility, responsive sizing, and retain the existing global reduced-motion policy. |
| Frontend release gates | **PASS** — 27 test files, 116 passing tests, 2 existing todos; TypeScript and Vite/PWA production build passed. |
| Backend regression | **PASS** — complete `pytest -q` suite passed. |

This final source-level polish does not change the strict runtime boundaries: ComfyUI needs its real local listener, cloud/provider capabilities need their valid configured credentials, and user-model/VSeeFace camera behavior needs the real Windows runtime and sender. No unavailable capability has been simulated or marked verified.


## Phase 18 — Safe Live VSeeFace Facial/Head Tracking Repair

| Requirement | Result |
|---|---|
| Live eyes | **IMPLEMENTED** — `Fcl_EYE_Close_L/R` is now treated as a closure weight (0 open, 1 closed) end-to-end. The previous browser inversion that could render open eyes as fully shut is removed. |
| Live pose protection | **IMPLEMENTED** — `vrm.update(dt)` now completes before final calibrated head and relaxed normalized-limb writes, so no downstream VRM update can restore a T-pose after the safety layer. |
| Motion scope | **IMPLEMENTED** — fresh VMC controls expression and bounded calibrated Head motion only. Spine, hips, shoulders, arms, hands, and root remain excluded from VMC mirroring and finish in the companion’s relaxed pose. |
| Voice lip sync | **PRESERVED** — TTS visemes retain mouth ownership during speech; external vowel/mouth data applies only when HINAA is not speaking. |
| User-visible transparency | **IMPLEMENTED** — the live control panel says exactly which motion is mirrored and that the body/arms remain protected. |
| Focused validation | **PASS** — bridge suite has 3 passing tests; frontend VMC/app suite has 27 files, 116 passing tests, and 2 existing todos; TypeScript passes. |

The supplied screenshot identifies a real Windows visual defect and drove this repair. Final visual proof after applying this branch remains **PENDING_USER_RUNTIME**, not automatically passed: it requires restarting the local API/frontend, hard-refreshing, reconnecting VSeeFace, and observing the actual selected model under a real camera sender.


## Phase 19 — Companion Playground and Smooth Expression Layer

| Requirement | Result |
|---|---|
| Upper-body companion stage | **IMPLEMENTED** — desktop avatar pane is widened and styled as a richer companion stage; the same existing canvas can enter a native full-screen HINAA playground. |
| Relaxed shoulders and arms | **IMPLEMENTED** — default HINAA profile now uses real rig-aware shoulder + upper-arm + forearm offsets calculated from cached rest transforms, producing a more natural distributed arm drop. |
| VSeeFace expression smoothness | **IMPLEMENTED** — visual application of incoming VMC expressions uses render-rate smoothing, preventing harsh packet/camera jitter. |
| Speech-aware emotion | **IMPLEMENTED** — subtle warm, curious, empathetic, celebratory, or concerned accents derive only from HINAA’s own response text, with multilingual regression coverage. |
| Lip-sync ownership | **PRESERVED** — TTS mouth visemes take precedence while speaking; non-speech VMC vowels apply only when HINAA is not speaking. |
| Facial readiness | **IMPLEMENTED** — live motion is no longer enough to assert expression mirroring. The UI requires observed `expression:*` blendshape channels and otherwise says it is waiting for blendshapes. |
| Release gates | **PASS** — 28 frontend test files, 120 passing tests, 2 existing todos; TypeScript, Vite/PWA production build, and full backend regression passed. |

Final real-world acceptance is still **PENDING_USER_RUNTIME**. After the branch is applied, the user must verify the actual selected Windows model in the actual browser: relaxed shoulders, clear upper-body portrait/playground, detected expression channel, smooth face response, calibrated head movement, and uninterrupted voice lip sync.
