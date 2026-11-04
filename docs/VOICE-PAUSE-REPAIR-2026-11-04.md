# Live voice pause and streaming repair

Changes are local, preserve previous repairs, and introduce no API credentials or paid provider calls during tests.

## Listening behavior

- `apps/web/src/features/audio/turnTakingController.ts`: resumed speech clears the previous continuous-silence count after two voiced frames, keeping a single noisy spike from resetting it.
- The sentence-completion check now matters. An incomplete or one-word partial waits for the bounded hard silence window rather than being dropped by the no-partial fallback.
- Default complete-partial timeout remains 22 frames, approximately 440 ms. Without partial transcripts, the controller waits 40 frames, approximately 800 ms. Incomplete recognized speech has a 60-frame, approximately 1200 ms ceiling. These are endpointing budgets, not total response latency.
- A pause followed by resumed speech increases the session's pause allowance by a small margin, bounded by the hard ceiling. This simple adaptation is not semantic prediction or model training. Pauses beyond the current window can still end a turn.
- Real microphone turns without partial transcripts are no longer suppressed solely because their audio durations match. Short sustained greetings meet the minimum speech duration.
- Normal sustained speech can interrupt while waiting for a provider. Playback retains stronger echo protection and the existing sustained barge-in requirement.
- `apps/web/src/features/audio/useLiveConversation.ts`: removes conflicting live pause overrides, publishes microphone/diagnostic meters at 10 Hz while processing and transmitting every audio frame, and avoids changing metrics state when the turn state is unchanged.

## Earlier audio delivery

`apps/api/hinaa_api/realtime.py` can hand a complete six-character opening sentence or a substantial comma-terminated opening clause to synthesis before the rest of the response completes. Decimal values and domain dots are not treated as sentence boundaries. A separate phrase count makes the first-phrase optimization apply only once, including on the WebSocket synthesis path. Later phrases still batch to avoid excessive tiny audio segments.

This removes avoidable buffering. It does not benchmark or reduce cloud inference/network time. The actual microphone path still uses post-commit transcription; native speech-to-speech is not added by this patch.

## Verification

From `apps/web`:

```powershell
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
```

Results: 98 files passed; **641 tests passed, 2 TODO**. TypeScript and production build passed. Existing large-bundle warnings remain.

From the repository root:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_realtime.py apps/api/tests/test_realtime_transport.py apps/api/tests/test_progressive_voice.py -o addopts= -q
```

Result: **21 passed**, one Google SDK deprecation warning. These use local test clients and mocked providers. The frontend hook-named test file tests state-machine scenarios, not actual browser microphone capture; the controller regressions exercise the real controller implementation.

New regressions cover a 600 ms pause and resumption, incomplete/one-word partials, short no-partial turns of matching duration, learned pause margins, the fast complete-sentence path, and first spoken phrase boundaries.

The production frontend assets were rebuilt and the supervisor-owned API was restarted. No public deployment was changed. Real speech-recognition accuracy, actual audible latency, microphone echo, and 3D/audio performance still require a human microphone session; these are not proven by green automated tests.

## Try locally

Open `http://127.0.0.1:5173/`, refresh to load the rebuilt frontend, and start a new live voice session. Say a sentence, pause around half a second, then continue. Verify the final transcript retains both halves, then check interruption while Hina is waiting and speaking. Use headphones to distinguish recognition problems from speaker echo. Push-to-talk remains available to explicitly finish longer thinking pauses without guessing their duration.

Rollback: reverse only this checkpoint's hunks in `turnTakingController.ts`, its test, `useLiveConversation.ts`, `realtime.py` and `test_realtime.py`. Rebuild the frontend and restart only the owned API. Do not reset whole files containing earlier repairs.
