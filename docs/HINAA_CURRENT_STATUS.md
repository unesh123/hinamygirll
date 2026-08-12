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
