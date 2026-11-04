# Streaming microphone text checkpoint — 2026-11-04

## Implemented locally

- Added `apps/api/hinaa_api/providers/streaming_stt.py`: per-utterance server-side recognition using existing credentials. Fixed English uses configured Deepgram; automatic/mixed and Nepali prefer configured ElevenLabs Scribe v2 Realtime. Deepgram-only Nova-2 automatic/Nepali requests retain batch fallback rather than silently selecting English. No API key is returned to the browser and no new provider credential was installed.
- Updated `apps/api/hinaa_api/realtime.py`: accepted audio frames go to recognition while recording; `stt.partial` events return before `audio.commit`. The final streaming result feeds the existing brain/TTS path. A missing, failed or unconfirmed final falls back to transcription of the complete original PCM buffer. A partial cannot become an authorized user turn on its own.
- Recognition runs outside the audio receive loop with a bounded 256-frame queue. Overflow falls back rather than returning a transcript with missing audio. Cancellation, replacement, disconnect, finalization and turn cleanup close the vendor connection. Streams open when speech starts, not whenever an idle microphone session exists.
- Updated `apps/web/src/features/audio/useLiveConversation.ts`: consumes recognition status, records transport diagnostics, clears stale drafts and per-turn partial timing, and cancels capture when paused. Existing partial/final handlers update the companion controller.
- Updated `apps/web/src/design-system/modes/WorkMode.tsx`: renders a visibly provisional user transcript in the chat and scrolls it into view. Finalization replaces that draft with the normal persisted user message. It does not submit interim text as commands.
- Updated `packages/contracts/schemas/phase-3-live-message.schema.json` to include the additive `stt.status` event.
- Added backend coverage in `apps/api/tests/test_streaming_stt.py`; updated the existing idle-window test double in `apps/api/tests/test_realtime.py` for the recognition argument. Added a draft/final replacement UI regression in `apps/web/src/design-system/modes/WorkMode.test.tsx`.
- Added `scripts/check_live_transcription.py` for explicit real-service smoke checks with a supplied PCM16 mono 16 kHz WAV. It does not record a microphone, create a Hina conversation, or invoke tools.

## Actual live speech-service checks

A Windows speech synthesizer produced a 4.575-second test WAV saying: “Hello Hina. Please help me plan my study schedule.” This was synthetic English speech, not a user microphone recording. Both services returned the expected sentence with punctuation and a provisional transcript before the audio finished.

| Service | First partial from test start | Connection ready | Final after commit |
|---|---:|---:|---:|
| ElevenLabs Scribe v2 Realtime | 3820 ms | Not measured on that run | 859 ms |
| Deepgram configured streaming model | 2812 ms | 2078 ms | 565 ms |

These are single smoke observations, not averages or latency guarantees. Deepgram's first partial followed connection readiness by about 734 ms. Opening the vendor connection is a substantial measured part of the initial delay. These results do not establish zero delay, accuracy on the user's microphone, Nepali/Hindi recognition quality, warm-session latency or end-to-end spoken-answer latency.

Evidence is local under `.runtime/streaming-stt-probe.json` (ElevenLabs) and `.runtime/streaming-stt-probe-deepgram-streaming.json` (Deepgram). Existing configured keys were used for these short paid-provider checks. Keys and environment files were not changed.

Repeat deliberately, since these commands use speech-service quota:

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 scripts/check_live_transcription.py --wav .runtime/hina-recognition-probe.wav --provider elevenlabs
apps/api/.venv/Scripts/python.exe -X utf8 scripts/check_live_transcription.py --wav .runtime/hina-recognition-probe.wav --provider deepgram
```

## Automated evidence

From the root:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_streaming_stt.py apps/api/tests/test_realtime.py apps/api/tests/test_realtime_transport.py apps/api/tests/test_realtime_identity_ticket.py apps/api/tests/test_progressive_voice.py -o addopts= -q
```

The broad run passed **40 tests**. After adding the final language-selection regression, the focused `test_streaming_stt.py` run passed **14 tests**. These cover partial-before-commit, stable finals, use of the stream result in the actual turn processor without a second transcription, complete-audio fallback, segmented text, cancellation/stale words, overflow, timeout, provider quota failure and language selection. Provider sockets and model replies in regression tests are mocked.

From `apps/web`:

```powershell
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
```

The full frontend run passed **642 tests**, with two existing TODOs; TypeScript and the production build passed. Existing large-bundle warnings remain. The chat regression checks provisional replacement and no interim submission, using jsdom rather than a real microphone.

## Runtime and limits

The frontend production assets were rebuilt and the verified supervisor-owned API was restarted. Refresh `http://127.0.0.1:5173/` and start a new live session to load this code. No public deployment was performed. The changes do not implement wake-word detection or native speech-to-speech inference.

Interim recognition is an evolving hypothesis: words may change before confirmation. Backend execution still begins only after the existing turn commit and confirmed transcript. A provider rejection can restore the old batch behavior; the voice diagnostics now report that fallback. Supported languages and API account permissions still apply.

Further speed work should measure persistent-connection lifecycle and regional network latency. Keeping a paid vendor stream open while nobody speaks has billing and cleanup consequences; this checkpoint does not silently add an unlimited idle connection. Do not describe a listening animation or a partial transcript as a completed understanding or action.

Rollback only this checkpoint's hunks and new files, preserving earlier voice, avatar, ComfyUI and unrelated work. Rebuild the frontend and restart the supervisor-owned API afterward; no key rollback is needed.

Primary protocol references: [ElevenLabs realtime STT](https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime), [Deepgram streaming audio](https://developers.deepgram.com/reference/speech-to-text/listen-streaming), [Deepgram interim/final segments](https://developers.deepgram.com/docs/understand-endpointing-interim-results).
