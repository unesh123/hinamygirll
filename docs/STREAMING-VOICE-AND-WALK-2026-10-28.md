# Streaming voice and walking-view repair — 2026-10-28

This checkpoint adds incremental audio delivery and fixes specific avatar/runtime defects. It does not establish human-equivalent animation, working autonomous PC control, or a restored public deployment.

## Implemented

- `apps/api/hinaa_api/speech_stream.py`: new `/api/v1/speech/synthesis/stream` and `/v1/speech/synthesis/stream` routes reuse the existing ElevenLabs WebSocket client. They stream NDJSON PCM frames and character alignment rather than collecting a complete phrase file. Empty output and upstream errors produce explicit failure records; cancellation aborts the upstream socket. Routes retain existing owner-auth middleware; no auth exemption was added. Explicit other voice engines and mock/local modes are rejected by this route and retain the existing synthesis path.
- `apps/api/hinaa_api/main.py`: registers those routes; Gemini Live's configured audio capability no longer claims verified chat health, a default text model, or measured sub-300-ms latency.
- `apps/web/src/features/audio/streamingSpeechAudio.ts`: reads network frames incrementally, validates PCM, converts character timing, handles fragmented network messages, and rejects truncated/error streams. Waits for first audio, not end-of-stream, before returning to the player.
- `apps/web/src/features/audio/progressiveSpeech.ts`: audio results can carry an ordered async audio stream.
- `apps/web/src/App.tsx`: streams ElevenLabs PCM through existing Web Audio scheduling while text generation continues. Uses the previous bounded fallback before the first audio frame. Devices without Web Audio retain file-based synthesis. A midstream failure is reported rather than replaying the already-spoken phrase through another provider.
- `apps/web/src/components/ui/AvatarPresence.tsx`: full-body camera fits both viewport axes, allows lateral walk travel and control clearance, and disables speech dolly/FOV zoom in full-body mode. Initial relaxed bone pose is applied before precise skinned-model bounds are measured, avoiding T-pose framing and the first-frame pose transition.
- `apps/web/src/features/avatar/fullBodyCamera.ts`: independently testable perspective-fit calculation.
- `apps/web/src/features/avatar/HinaFloatingOverlay.tsx`: hidden or non-walking widgets no longer run the React walk-state animation loop. Hidden documents skip walk-state updates.
- `apps/web/src/design-system/modes/CompanionDock.tsx`: labels the procedural motion as a walking preview.
- `apps/web/src/features/providers/utils/resolveProviderSelection.ts`: automatic text-brain selection no longer treats Gemini Live audio availability as evidence of healthy chat inference.

Test files added/updated: `test_speech_stream.py`, `streamingSpeechAudio.test.ts`, `fullBodyCamera.test.ts`, `HinaFloatingOverlay.test.tsx`, `resolveProviderSelection.test.ts`, and the existing `App.test.tsx` speech fixture. Earlier dirty files and the preceding latency/lip-sync changes were retained. RAG, Freepik, model binaries and environment credentials were not edited.

## Actual results

```powershell
pnpm --dir apps/web test
pnpm --dir apps/web build
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_speech_stream.py apps/api/tests/test_elevenlabs_ws_stream.py apps/api/tests/test_elevenlabs_unit.py apps/api/tests/test_turn_preparation_latency.py -o addopts= -q
git diff --check
```

- Final frontend: **98 files passed, 634 tests passed, 2 todo**.
- Focused backend: **52 passed**, one Google SDK deprecation warning.
- Build includes TypeScript: passed. Large bundle warnings remain.
- Diff whitespace check passed; existing Windows line-ending conversion warnings remain informational. Mixed line endings in AvatarPresence/main were handled while preserving unchanged raw lines.
- Unit tests use fake vendor sockets, fake network streams, controlled clocks, and mocked DOM/animation scheduling. They prove first-frame delivery before stream completion, order, alignment conversion, malformed/truncated stream failure, cancellation cleanup, camera-fit geometry and the hidden-widget lifecycle. They do not measure physical speaker output or GPU frame times.

## Live ElevenLabs probe

One bounded request using the backend's existing configuration and synthetic text, `Hello. I am ready.`, through the actual local streaming endpoint:

| Measurement | Observation |
|---|---|
| HTTP status | 200 |
| First audio frame | 1,207 ms |
| Completed response | 1,588 ms |
| Audio frames | 2 |
| Approximate PCM bytes | 64,647 (base64-length estimate) |
| Terminal event | done |

This verifies a real upstream ElevenLabs stream and incremental local HTTP delivery. It is one observation, not a latency percentile, an improvement ratio, a voice-quality listening test, or total user-request-to-audible-speech latency. The LLM's initial thinking time comes before synthesis.

## Brave browser verification and failed chat check

Used the existing Brave tab at `http://127.0.0.1:5173/`, rather than opening another signed-out browser. After the camera settled, the walking view showed the head and feet. It was also checked without the separate floating toy widget covering the model. This is visual framing evidence, not proof of realistic foot contact, hand gestures, or measured FPS.

Submitted one synthetic two-sentence voice check through the UI. That **did not establish a working end-to-end conversation**: the selected Gemini Live route and its fallback chain failed, and only the existing temporary acknowledgement was visible. Logs showed provider authentication failures, timeouts and rate limits. The false audio-ready/chat-ready selection was subsequently corrected and tested; no further successful chat generation is claimed.

Sanitized provider status observations after the final backend restart:

- XKiro and CX Gateway: last inference call reported authentication failure; unavailable.
- Gemini text: last call timed out; degraded.
- Experiential: rate-limited; degraded.
- Gemini Live: configured audio only; session performance unverified; degraded.

Model-list discovery returning HTTP 200 does not prove inference authorization or quota. These accounts need functioning inference access before reliable fast conversation can be verified. No new credentials were created, changed, exposed, or requested in chat.

## Runtime and remaining work

Built frontend and updated backend run on loopback ports 5173 and 8000. Logs/build/test evidence are in `.runtime/latency-repair/`. Public Vercel deployment and ingress were not changed. Local auth in the observed browser is development auth, so this is not a Clerk-authenticated production test.

Still outstanding: successful browser text-plus-audible-audio verification with a working brain, microphone duplex/interruption measurements, mobile browser/device testing, desktop/mobile frame-time profiling, authored/retargeted walk clips and foot contact, rig-specific hand and facial calibration. The existing procedural gait remains procedural; pose-gallery images are not animation clips.

Official references reviewed: [ElevenLabs real-time TTS](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts), [VRM Animation](https://vrm.dev/en/vrma/).

## Rollback limited to this checkpoint

Review and reverse only this checkpoint's hunks and remove only its new files when unused. Preserve the preceding dirty changes in services.py, App.tsx/App.test.tsx, the three avatar playback-clock files, speechFallback files, and LATENCY-REPAIR-2026-10-28.md. Do not reset whole files or discard unrelated RAG/Freepik work. Rebuild the frontend and restart only the identified local backend after reversal; no public deployment rollback is required.
