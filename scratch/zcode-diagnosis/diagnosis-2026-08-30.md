# HINAA Diagnosis — Live Voice + @ Composer (2026-08-30, read-only pass)

Scope: symptom-level diagnosis only. No files modified, no servers touched, no tests/builds run.
Runtime backend state assumed per prompt: `127.0.0.1:8000` healthy; elevenlabs STT+TTS healthy; gemini-live healthy; azure disabled.

---

## (a) Live-voice chain with break points

### Chain diagram

```
[TalkMode mic dock]  TalkMode.tsx:386-394
        │ onStartVoice
        ▼
[App.tsx:786]  interruptPlayback(); live.start()
        ▼
[useLiveConversation.start  useLiveConversation.ts:851]
  ├─ getUserMedia (echoCancellation+NS+AGC)        :872-880
  ├─ AudioContext(48k) + resume if suspended       :881-885
  ├─ audioWorklet.addModule("/worklets/pcm-capture.js") :886   ✅ file exists (apps/web/public/worklets/pcm-capture.js), 320-sample/640-byte 16 kHz frames — inside backend FrameDescriptor ge=640 le=1280 (realtime.py:47)
  ├─ ⚠ BP-E guard: providers not loaded & no mode → error   :913-920
        ▼
[WS connect  ws(s)://host/api/v1/realtime  :776, :115-122]
  Vite proxy ws:true rewrite /api→127.0.0.1:8000 (apps/web/vite.config.ts)
  backend mount  @app.websocket("/v1/realtime")  (apps/api/hinaa_api/main.py:622)
  session.hello {providerMode: routing.activeMode ?? "mock"}   :782-802
        ▼
[session.ready  server realtime.py:159-173  → client :452-463]  ready.current=true
        ▼
[AudioWorklet frames → handleWorkletFrame :363-426]
  ├─ TurnTakingController.process (turnTakingController.ts:117-273)
  │    ⚠ BP-A: dynamicStartThreshold = max(0.012, noiseFloor*2.2+0.008)  :146-149
  │         → config.startThreshold (0.006 @ useLiveConversation.ts:863) and DEFAULT (0.003, :47) are DEAD
  ├─ ⚠ BP-D: sendFrame drops frames while !ready.current  :317  (preRoll caps at 10 frames ≈ 200 ms, :406-408)
  ├─ speechStart → audio.start (:356) → frames → audio.commit (:415-419)
  ├─ barge-in double gate: dynamicBargeInThreshold ≥0.12 (:150-153) AND level ≥ 0.22 (useLiveConversation.ts:379)
        ▼
[backend _control  realtime.py:205-303]
  ├─ mock mode only sends stt.partial  :263-274   (real modes: NO partials → client soft-commit needs transcript,
  │                                                falls back to silence-commit turnTakingController.ts:233-244)
  ├─ audio.commit → _process_turn :305
  │    ├─ STT: services.transcribe → ProviderRouter.stt (services.py:356-376):
  │    │     mock→mock · local→local_stt · else Deepgram if configured → ElevenLabs if configured (✅ healthy) → local
  │    ├─ empty transcript → voice.error STT_EMPTY_TRANSCRIPT + turn.cancelled  :334-357
  │    │     ⚠ BP-F: client handleServerEvent has NO "voice.error" branch (useLiveConversation.ts:428-774) — detail swallowed;
  │    │              only the follow-up turn.cancelled (:731-741) is surfaced
  │    ├─ Brain: create_live_plan → ProviderRouter.llm (services.py:380+) by providerMode; brainModel only for real set
  │    ├─ TTS: synthesize_text per clause (realtime.py:469-504); stream_real_audio for real brain set :380-382
  │    │     ProviderRouter.tts (services.py:545-594): Deepgram(hiro) → FishAudio if voice id set → ElevenLabs ✅ → Azure(disabled) → local
  │    └─ turn.complete {ttsRequested, ttsStatus}  :597-615
        ▼
[client tts.audio → playback queue chain  useLiveConversation.ts:558-664]
  ├─ decodeAudio (base64→Blob) :133-139 · mediaType audio/mpeg for elevenlabs mp3 (realtime.py:98-116) ✅
  ├─ playback.play (useAudioPlayback.ts:115-210)
  │    ⚠ BP-C: ALL failure paths return SILENTLY:
  │       ensureGraph throw → return :121-123 · resume fail → return :124-130
  │       decodeAudioData fail → return :135-141 · source.start throw → cleanup+return :179-185
  │     → queue counters (decodedBuffers incremented at useLiveConversation.ts:637, decremented only in onStarted :642)
  │       never drain → turn.complete handler sees audioStillPending → 30 s drain watchdog :1059-1078
  ├─ playing→false effect drives Speaking→Listening :266-308
        ▼
[turn.complete routing  :665-730]  ttsStatus failed → "read my reply below" :709-715
```

### Break points (ordered by likely impact)

| # | Where | What | Class |
|---|-------|------|-------|
| BP-A | `apps/web/src/features/audio/turnTakingController.ts:146-149` (+ dead config at `useLiveConversation.ts:862-869`, `turnTakingController.ts:39-50`) | VAD speech-start threshold is overridden: `max(0.012, noiseFloor*2.2+0.008)`. The tuned `startThreshold: 0.006` passed by `start()` is ignored (DEFAULT `0.003` also dead). On quiet/low-gain mics (RMS ≈ 0.005–0.02 speech) `audio.start` may never fire → nothing is committed → 30 s stuck timer (`useLiveConversation.ts:1021-1033`) errors out. Noise-floor adaptation (:141-143) raises the bar further in noisy rooms. | candidate (high) |
| BP-B | `useLiveConversation.ts:852` vs error paths `:742-773`, `:941-953`, `:1021-1033`, `:1040-1055` | Post-error zombie session: `start()` early-returns while `active.current` is true, but **no error path resets `active.current`** (only `stop()` :979 does). After ANY error (timeout, provider, AUDIO_*) the mic button shows "Start voice" (returned `active` :1101 is false) yet tapping it is a silent no-op → "does not listen" persists until page reload. | candidate (high) |
| BP-C | `useAudioPlayback.ts:121-141,179-185` + queue counters `useLiveConversation.ts:637/642`, watchdog `:1059-1078` | Every playback failure (AudioContext blocked, decode failure, source.start throw) fails silently; queue never drains; Speaking state lingers up to 30 s then force-recovers. Matches "answers in text but no voice". | candidate (medium) |
| BP-D | `useLiveConversation.ts:317` | Audio frames are dropped (not buffered) when `session.ready` hasn't arrived yet; preRoll only preserves 10 frames ≈ 200 ms. Early speech after connect is lost. | candidate (low) |
| BP-E | `useLiveConversation.ts:913-920` | If the user taps the mic before provider statuses load (auto mode ⇒ `activeMode=null`, `providersLoaded=false`), start() aborts to error — which then also hits BP-B. | candidate (low) |
| BP-F | `useLiveConversation.ts:428-774` (no `voice.error` branch) vs `realtime.py:334-357,620-627` | Backend emits `voice.error` (STT_EMPTY_TRANSCRIPT, VOICE_TURN_TIMEOUT); client never handles the type — user sees only the generic turn.cancelled text. Diagnostic loss, not silence. | candidate (low) |
| BP-G | `realtime.py:263-274` | `stt.partial` only sent in mock mode. Real-mode commits depend solely on the silence-commit path (`turnTakingController.ts:233-244`): ≥4 voiced frames then ≥38 quiet frames (~760 ms). Functional but slower/fragile; soft end-of-turn (`:195-199`) is unreachable without partials. | candidate (info) |
| BP-H | `useLiveConversation.ts:379` + `turnTakingController.ts:150-153` | Barge-in requires level ≥ 0.22 AND 8 sustained frames ≥ max(0.12, dynamic). With echoCancellation on this is safe against self-echo but makes interruption very hard (UX, not silence). | candidate (info) |

Verified-healthy links (no break found): worklet file+frame contract, WS URL/proxy/mount, STT→ElevenLabs selection for real modes, TTS→ElevenLabs selection, mediaType labeling (`realtime.py:98-116`), generation/sequence guards, autoplay unlock overlay (`App.tsx:322-342,851-883`).

Note: `useLiveConversation.ts:365-368` setState ×2 per 20 ms frame (50 Hz) — render churn, worth watching, not a break.

---

## (b) @ composer commands — table with break points

### Where the @ system actually lives (and dies)

- The ONLY @ trigger detection: `PremiumComposer.detectComposerTrigger` — `apps/web/src/components/ui/PremiumComposer.tsx:73-94`; popup `PowerUpMentions` rendered at `:173-186`; tag insertion `:127-149`.
- **`PremiumComposer` is never rendered.** Imported at `apps/web/src/App.tsx:21`, zero JSX usages. The Sakura OS UI renders:
  - TalkMode — no composer at all (`TalkMode.tsx` has only the voice dock).
  - WorkMode — an **inline `<textarea>`** (`design-system/modes/WorkMode.tsx`, textarea ≈ line 436, send ≈ 479); it imports only *types* from ChatComposer (`WorkMode.tsx:18`) and receives `powerUps={[]}` + `onPowerUpToggle={() => {}}` (`App.tsx:834-835`).
- `features/chat/components/Composer.tsx` — dead code: no importers anywhere; has no @ support.
- `handlePowerUp` map (`App.tsx:602-624`) — the action dispatcher — can therefore never fire. Even if it did, every action only opens a panel; none executes the tool, and the inserted literal tag `"@search …"` (`PremiumComposer.tsx:135`) goes verbatim to `POST /api/v1/conversations/turns:stream` (`features/providers/backendConversationProvider.ts:50`). The backend has **no @-tag parser**: `_inject_deterministic_tool_intents` (`apps/api/hinaa_api/services.py:762+`) matches natural-language patterns anchored at `^\s*(search|find|open…)`, which `"@search …"` fails because of the leading `@`.

**Net: typing `@` in the running app does nothing — one shared entry-level break.** Per-command breaks below assume the entry is repaired.

| Command | action | Intended behavior | Where it breaks (after entry repair) | Class |
|---|---|---|---|---|
| `@search` | search-web | Web search w/ sources | Panel-only (`App.tsx:606` sets contextMode research); no search invoked; tag text unanswered by tools. Backend has tinyfish.py/browser.py but unreachable from this path | UI wiring + no dispatch |
| `@image` | image-search | Image search | Panel-only (`:607`); backend image_search intent exists (services.py:770+) but `@image` text won't match its patterns | UI wiring |
| `@generate` | generate-image | Generate artwork | Panel-only (`:608`); LocalImageStudio exists (`App.tsx:654-659`) but @ doesn't open it (contrary to sibling `@humanize` which does open a studio) | UI wiring (fix = call openImageStudio) |
| `@browser` | browser-navigate | Navigate site | Panel-only (`:609`); browser tools exist backend-side (tools/browser*.py) | UI wiring |
| `@read` | browser-read | Extract/summarize page | Panel-only (`:610`); same | UI wiring |
| `@code` | write-code | Code help | Only nav switch to Tools (`:611`); no dedicated code tool; brain handles plain text anyway | UI wiring (low impact) |
| `@music` | play-music | Play on YouTube | Panel-only (`:612`); tools/youtube.py exists | UI wiring |
| `@email` | check-email | Check/send email | Panel-only (`:613`); tools/email.py exists | UI wiring |
| `@calendar` | show-calendar | View schedule | Nav switch (`:614`); **no backend calendar tool** (no calendar.py in tools/) | missing backend route |
| `@files` | search-files | Search/manage files | Nav switch (`:615`); no file-search tool (only document_ingestion.py) | missing backend route (partial) |
| `@memory` | remember-this | Save/recall memory | Opens MemoryPanel (`:616`); memory_service persists backend-side | UI-only; closest to working |
| `@agent` | agent-mode | Autonomous task | Nav switch (`:617`); tools/browser_agent.py exists | UI wiring |
| `@automate` | automation | Tool pipelines | Nav switch (`:618`); tools/browser_automation.py exists | UI wiring |
| `@system` | system-open | Open apps/system actions | Nav switch (`:619`); **no backend system-control tool** (vmc_bridge.py is avatar VM, not OS control) | missing backend route |
| `@export` | export | Download/save results | Nav switch (`:620`); **no export tool** | missing backend route |
| `@humanize` | open-humanizer | Text Humanizer Studio | `openHumanizerStudio` opens a real drawer (`App.tsx:621,661-666`) | **would work once entry is repaired** |

Slash `/` variants share every break (same handler, `PremiumComposer.tsx:180-186`).

---

## (c) Evidence states & remaining gaps

**Observed (static, verified in code this pass)**
- PremiumComposer never mounted; WorkMode inline textarea; `powerUps={[]}` + no-op toggle (`App.tsx:834-835`).
- No @-tag parsing anywhere in `apps/api` (`_inject_deterministic_tool_intents` is natural-language only, `^`-anchored).
- `startThreshold` config dead at `turnTakingController.ts:146-149`.
- `active.current` never reset by error paths; `start()` early-return at `:852`.
- Silent-return failure paths in `useAudioPlayback.play`.
- `voice.error` unhandled client-side.
- `stt.partial` mock-only (`realtime.py:266`).
- Worklet present and inside backend frame contract; WS path/proxy/mount correct; STT/TTS routers resolve to healthy ElevenLabs for real brain modes.

**Observed (user-reported, not reproduced here)**
- "Hina does not listen" and "does not answer with voice" during live conversation.

**Candidate (code-suggested, needs runtime confirmation)**
- BP-A blocking `audio.start` on the user's mic/room (would explain "does not listen").
- BP-B making the failure sticky (explains why it "never" works after the first failure).
- BP-C silent playback failure (would explain "no voice" with text present).
- Mode-specific: if the stored provider preference is `local`/`groq`, STT goes to `local_stt` (`services.py:360-361`) which is likely uninstalled → every turn fails. Auto mode avoids this (AUTO_PRIORITY picks a healthy real brain).

**Gaps (what a follow-up runtime pass should capture)**
- `live.diagnostics` from the existing VoiceDiagnosticsDrawer for one failing session: `currentStage`, `rmsLevel`, `chunksSentPerSecond`, `lastError`, `voiceRoute` — this alone discriminates BP-A (rmsLevel never crossing ~0.012, stage stuck at `listening`) from BP-B (lastError set, stage `error-*`) and BP-C (`tts-audio` reached, `playbackState` idle, queue counters stuck).
- Backend log lines `realtime: <<< …` (logger `hinaa.realtime`) for one turn — confirms whether `audio.start`/`audio.commit` ever arrive.
- Which `providerMode` the user actually runs (Settings → Provider; or `voiceRoute.brainProvider` in diagnostics).

---

## (d) Ordered minimal-risk fix plan (NOT implemented)

1. **Unstick post-error sessions (BP-B).** In `useLiveConversation`, reset `active.current = false` (or call the existing `stop()` teardown) on: `error` event (`:742`), stuck-listening timeout (`:1030`), brain timeout (`:1048`), and the `start()` catch (`:941`). Smallest safe change: make the returned `start` call `stop()` first when `status === "error"`. Zero protocol impact.
2. **Restore configured VAD threshold (BP-A).** Use the passed `startThreshold` as the floor: e.g. `dynamicStartThreshold = max(config.startThreshold, min(0.012, noiseFloor*2.2 + 0.008))` in `turnTakingController.ts:146-149`, or simply honor `config.startThreshold` when `noiseFloor` is below an ambient cap. Pure client change; covered by existing `turnTakingController.test.ts` patterns.
3. **Make playback failures observable (BP-C).** In `useAudioPlayback.play`, replace silent `return`s with a rejection or an `onError` callback, and decrement/flush queue counters in a `finally` in the `tts.audio` queue chain (`useLiveConversation.ts:585-664`) so the drain watchdog resolves in seconds, not 30 s.
4. **Handle `voice.error` (BP-F).** Add a branch in `handleServerEvent` mapping known codes (STT_EMPTY_TRANSCRIPT, VOICE_TURN_TIMEOUT) to the same userMessages table (`:756-766`) without changing state machine transitions.
5. **Re-wire the @ entry (composer).** Port `detectComposerTrigger` + `PowerUpMentions` into the Sakura composer (or render `PremiumComposer` from WorkMode in place of the inline textarea). Lowest-risk first step: keep the inline textarea, add trigger detection + popup; wire `onPowerUp` to the existing `handlePowerUp` map (`App.tsx:602`).
6. **Give @-tags backend semantics.** Preferred: translate the tag into an explicit tool request client-side using the already-plumbed `visibleActions` (`CommitMessage` realtime.py:54 → `TurnRequest` :514) instead of sending literal `@search` text. Alternative: strip `@tag ` client-side and emit the matching natural-language prompt so `_inject_deterministic_tool_intents` matches. Do not change the WS protocol.
7. **Reconcile palette vs backend.** For `@calendar`, `@system`, `@export`: add backend tools or remove/replace the palette entries; `@files` needs a real file-search tool (document_ingestion exists but isn't search).
8. **Optional hardening (later):** pre-Roll depth (BP-D), providers-loading race (BP-E), barge-in sensitivity tuning (BP-H), per-frame setState throttling at `useLiveConversation.ts:365-368`.

Validation after each step: run only the targeted vitest specs (`turnTakingController.test.ts`, `useLiveConversation.test.ts`, `PremiumComposer.test.tsx`) plus one manual live session with the diagnostics drawer open.
