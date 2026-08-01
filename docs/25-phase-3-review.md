# Phase 3 review gate

## Outcome

Phase 3 live streaming and interruption is implemented through the offline, no-provider-call gate on `phase/3-live-streaming`. Phase 2 is preserved at local checkpoint `d8653ef`. The WebSocket mock path, AudioWorklet/VAD client, partial/final protocol, streamed safe text, validated TurnPlan, ordered phrase audio, voice identity metadata and cancellation generation are present. Phase 3 remains uncommitted and nothing was pushed.

No Azure or Gemini request was made during implementation or automated validation. Real continuous recognition, real Gemini first-token behavior, Hemkala/Sagar streaming playback, acoustic echo and physical Android behavior remain untested until the owner grants a fresh capped streaming-test approval.

## Architecture and protocol decisions

- `/v1/realtime` uses protocol `1.0`. JSON control descriptors carry session, turn, generation, sequence and monotonic timestamps. Each `audio.frame` descriptor is immediately followed by a raw PCM-S16LE binary frame.
- Browser capture uses an AudioWorklet and emits 320-sample/20 ms frames at 16 kHz mono. The server accepts 640–1280 bytes (20–40 ms), rejects odd/mismatched frames, caps one turn at 320,000 bytes and applies a 35-second idle timeout.
- The client uses ten frames of pre-roll, three consecutive voiced frames to start and 35 quiet frames (about 700 ms) to commit. Silence/noise never becomes a Gemini request. Echo cancellation, noise suppression and automatic gain control are requested from the browser.
- Speaker mode uses a stricter barge-in threshold than headphone mode. Local playback stops before the `interrupt` event is sent. Both client and server advance one monotonic generation and ignore older work, including queued audio.
- Azure live STT uses one continuous `PushAudioInputStream`/recognizer per utterance and forwards partial/final callbacks. Fixed `ne-NP` and auto `ne-NP`/`en-US`/`hi-IN` are selectable for later measurement. Neither mode is called more accurate before the approved benchmark.
- Gemini live mode makes one streamed text request, sanitizes arbitrary chunks and displays only text deltas. Emotion, gesture and other performance controls are constructed and validated server-side after the text completes; invalid plans enter a safe error/idle path.
- TTS splits at useful sentence boundaries, synthesizes ordered segments and prevents overlap. Browser playback uses one promise queue and an analyser-smoothed jaw signal. This is amplitude lip motion, not visemes.
- Heartbeats run every 15 seconds. Unexpected disconnect uses at most three exponential reconnect attempts. Manual stop closes the socket, microphone tracks, worklet/source nodes, Web Audio context and playback queue.
- Phase 2 REST/NDJSON, record-then-process, text, deterministic mock, reduced-motion, text-only and WebGL fallback paths remain available.

## Voice identity and calibration

The immutable development mapping is:

| Companion | Requested Azure voice | Locale |
|---|---|---|
| Hinaa | `ne-NP-HemkalaNeural` | `ne-NP` |
| Hiro | `ne-NP-SagarNeural` | `ne-NP` |

There is no silent browser or different-voice fallback. Successful TTS events expose requested and actual safe voice names; a missing voice produces `TTS_VOICE_UNAVAILABLE` and preserves text.

Natural, Soft and Lively are bounded server-side SSML rate/pitch/volume presets. They are development calibration choices, not a claim that one is “best.” The calibration sample button is disabled pending separate live-call approval.

Hemkala and Sagar are standard Azure Nepali neural voices, not custom anime voices. A truly unique Hinaa identity later requires a licensed, consenting voice actor or an approved custom-voice dataset. Copying an anime character or actor is outside scope.

## Created files

```text
apps/api/hinaa_api/realtime.py
apps/api/hinaa_api/voice_profiles.py
apps/api/tests/test_realtime.py
apps/web/public/worklets/pcm-capture.js
apps/web/src/features/audio/liveVad.ts
apps/web/src/features/audio/liveVad.test.ts
apps/web/src/features/audio/useLiveConversation.ts
packages/contracts/schemas/phase-3-live-message.schema.json
scripts/start-phase3.ps1
docs/25-phase-3-review.md
```

## Modified files

```text
README.md
apps/api/README.md
apps/api/hinaa_api/__init__.py
apps/api/hinaa_api/config.py
apps/api/hinaa_api/main.py
apps/api/hinaa_api/models.py
apps/api/hinaa_api/providers/azure_speech.py
apps/api/hinaa_api/providers/gemini.py
apps/api/hinaa_api/services.py
apps/api/tests/test_api.py
apps/api/tests/test_contracts.py
apps/web/README.md
apps/web/src/App.css
apps/web/src/App.tsx
apps/web/src/features/audio/useAudioPlayback.ts
apps/web/src/features/companion/useCompanionController.ts
apps/web/tests/e2e/mobile.spec.ts
apps/web/vite.config.ts
docs/17-roadmap.md
docs/22-requirements-traceability-matrix.md
docs/DEPENDENCY_BASELINE.md
openapi/hinaa-api.yaml
packages/contracts/README.md
```

No dependency manifest changed because Phase 3 uses browser platform APIs, existing FastAPI WebSockets and the already pinned Azure/Gemini SDKs. No credential/environment file or owner VRM/ZIP asset was read, modified, staged or listed as a deliverable.

## Validation evidence

Offline/no-provider-call results at this review gate:

```text
Backend Ruff format/lint     PASS
Backend strict mypy         PASS — 15 source files
Backend pytest              PASS — 20 tests
Frontend Prettier/Oxlint    PASS
Frontend TypeScript         PASS
Frontend Vitest             PASS — 22 tests
Mobile/realtime E2E         PASS — 14 tests, Pixel 5 + 320×568
Production PWA build        PASS — 8 precache entries
Frontend pnpm audit         PASS — 0 known vulnerabilities
Backend pip-audit           PASS — 0 known vulnerabilities
Blueprint/contracts         PASS
```

Tests cover protocol schema validation, binary frame bounds, duplicate/gap/stale handling, silence rejection, partial/final ordering, arbitrary text chunks, TurnPlan validation, phrase segmentation, ordered audio metadata, interruption generation, VAD start/commit, speaker echo threshold, permission denial, mobile layout and a synthetic WebSocket turn through the Vite proxy. They do not fabricate real provider success.

## Latency targets and evidence boundary

Development UI labels these as goals, not achieved claims:

| Milestone | Goal |
|---|---:|
| useful STT partial | ≤500 ms from speech |
| final transcript | ≤900 ms after speech end |
| Gemini first text | ≤800 ms after final transcript |
| first audible audio | ≤1.8 s after speech end |
| local playback stop on barge-in | ≤150 ms |

Five isolated in-process mock turns (credentials explicitly blank and environment-file loading disabled) measured: STT median/max 0/0 ms, first mock text 0/0 ms, mock LLM stream 92/100 ms, mock WAV synthesis 14/16 ms and total server turn 110/117 ms. These values detect local regressions only; they are not evidence for Azure/Gemini/network, browser playback or speech-end latency. Real target results remain **not tested**.

## Local run and secure-device boundary

From the repository root:

```powershell
.\scripts\start-phase3.ps1
```

PC loopback review: `http://127.0.0.1:5173/`. The launcher reloads API version `0.3.0` without Uvicorn reload and leaves provider mode controlled by the UI (mock by default).

Android microphone capture requires a trusted HTTPS origin. Use the certificate workflow already documented in Phase 2 and launch with `-Https`; never test Android microphone over insecure LAN HTTP or bypass a certificate warning. Public deployment must use publicly trusted TLS.

## Provider call and quota record

- Azure STT calls during Phase 3 implementation: **0**
- Gemini calls during Phase 3 implementation: **0**
- Azure TTS calls during Phase 3 implementation: **0**
- Voice calibration sample calls: **0**
- Quota/cost indication: **none**, because no live provider call was made
- Azure resources modified: **none**

The owner reports the Azure Speech resource is Free F0; the application does not modify or independently prove the portal tier.

## Remaining risks and Phase 4 recommendation

- Real callback ordering and latency vary with Azure region/network and must be measured in the capped live test.
- The fixed-vs-auto language decision needs the same short Nepali/Romanized/code-switched set under comparable acoustic conditions.
- Browser AEC and local VAD thresholds need speaker/headphone tests on the target PC and a trusted-HTTPS Android device. Mock energy fixtures cannot prove echo resistance.
- Phrase TTS reduces time-to-first-audio but Azure synthesis returns each phrase as a complete WAV; provider-native incremental audio would require a separately evaluated transport.
- Reconnect is session restart, not replay/resume. It intentionally avoids replaying captured audio.
- Audio is in memory only, but a production pilot still needs authentication, origin enforcement, rate limits and per-user session ownership from later phases.
- Amplitude jaw motion is intentionally approximate. Phase 4 should add the shared performance clock/viseme layer and polished licensed motion without changing the voice identity boundary.

Do not begin Phase 4, commit or push. After owner review, request a fresh explicit authorization for at most three short live streaming turns. Stop at the first blocking provider, quota, authentication, playback or microphone failure and return to mock mode after the cap.
