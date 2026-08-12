# HINAA Current Runtime Status

**Plan start:** 2026-08-12 UTC  
**Baseline commit:** `a1481389a9debce4a7f89a01cc9d7d00367fd80c`  
**Safety checkpoint:** `checkpoint/hinaa-evidence-plan-20260812T064546Z`  
**Repository state at checkpoint:** clean `main...origin/main`.

| Priority phase | Status | Evidence / next required runtime proof |
|---|---|---|
| 1. Reliability and chat recovery | IN PROGRESS | Controlled provider failure must finalize the turn, stop processing, unlock the composer, and permit a successful next message without refresh. |
| 2. Canonical assistant turns | PENDING | Detailed `displayText`, concise `spokenText`, refresh-safe rendering, and no raw JSON in visible or spoken content. |
| 3. AgentRouter | PENDING | Safe diagnostic completion using its actual configured protocol, including streaming and composer recovery. |
| 4. Professional answer | PENDING | Real technical answer with structured display output and concise speech summary. |
| 5. ComfyUI chat generation | PENDING | One real image visible in chat and after refresh; four real variations arriving progressively. |
| 6. Browser automation | PENDING | One approved Netflix navigation resulting in exactly one tab/window. |
| 7. Hindi and Nepali routing | VERIFIED (text) | Both required native-script prompts completed through the live Demo chat. Azure TTS routing is configured, but actual Azure audio remains unavailable without credentials. |
| 8. Complex local workflow | PENDING | Task tree, sources, comparison, sequential image results, project artifacts, and verified completion. |
| 9. Avatar lab and ownership integrity | PENDING | No dummy owner records; avatar controls remain persisted and stable. |
| 10. Production readiness | PENDING | Final local runtime check and evidence dossier. |

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
