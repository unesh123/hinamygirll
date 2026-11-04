# Local runner and responsive voice checkpoint

The existing supervisor was started in local production-preview mode on 2026-11-04. The API and frontend returned HTTP 200; runner state also reported the authenticated desktop bridge ready. No tunnel or deployment was requested. Earlier repair changes remain in the working tree.

## Start and stop

From the repository root in PowerShell:

```powershell
.\scripts\start-live.ps1
```

The launcher now defaults to local production preview. `-Dev` selects the frontend development server. Public tunnels and deployment recovery require explicit flags; do not use those for a local restart.

Open `http://127.0.0.1:5173/`. Inspect `.runtime/live/runner-state.json` for fresh timestamps and API/web/desktop health. The runner checks services approximately every three seconds and restarts its own unhealthy children after repeated failures and a retry cooldown. It does not kill another process occupying a port. Health is not proof of authenticated voice or task execution.

To request a clean stop:

```powershell
New-Item -ItemType File -Path .runtime/live/stop-requested -Force
```

The supervisor closes only its owned child processes. These are local process sessions, not a Windows service or boot-time installation; closing the host or shutting down the PC can stop them. Run the launcher again when needed. No new startup task was installed.

## What currently adds voice delay

Inspection of `apps/web/src/features/audio/turnTakingController.ts` shows an approximately 440 ms end-of-turn pause and a 700 ms hard silence ceiling. These waits distinguish hesitation from a finished sentence; setting them to zero would cut off speech.

In `apps/api/hinaa_api/realtime.py`, the current turn path transcribes captured audio after commit, then streams the model response and progressively synthesizes speech. ElevenLabs synthesis socket setup overlaps the brain step, but transcription still precedes it. A WebSocket called “realtime” does not make this entire pipeline native speech-to-speech.

No dedicated always-on “Hey Hina” keyword detector was found in the inspected frontend/backend source. Browser voice typing is not a dedicated on-device wake-word engine. Removing filler in the previous repair did not install one or eliminate inference latency.

## Recommended next voice milestone

1. User explicitly enables microphone and hands-free mode. Keep a local keyword detector ready while enabled; show listening state and a mute control. For Porcupine, obtain an AccessKey and a custom “Hey Hina” Web/WASM keyword model. A detector does not require a local general-purpose LLM.
2. On detected wake word, show an immediate visual listening response or play a short local earcon. Distinguish this acknowledgement from a generated answer. Preserve a short microphone pre-roll so words spoken immediately after the wake phrase are not lost.
3. Keep the authorized voice connection and playback audio context ready. Use streaming recognition or a native speech-to-speech transport to avoid waiting for a complete transcription before processing the turn.
4. Support interrupting playback, cancelling the old turn and dropping stale buffered audio. Keep heavy tool work separate from the conversational response path; do not claim an unfinished action succeeded.
5. Record wake detection, end-of-speech, recognition final, first text, first audio received and first audio played. Compare median and slow-tail latency on the actual PC/network before tuning pauses or changing providers.

For this 8 GB laptop GPU, my recommendation is local keyword detection plus cloud conversational inference, with optional local inference as a benchmarked fallback. Local image generation and a large local LLM can compete for the same GPU memory. “Local” does not automatically mean faster, and training is not the first fix for buffering and transcription delays.

Provider credentials and consent are needed before wiring a new paid speech service. None were added or changed here. No live wake-word accuracy, end-to-end voice latency or microphone playback was verified in this runner check. Zero delay is not physically achievable.

Primary references: [Porcupine Web setup](https://picovoice.ai/docs/quick-start/porcupine-web/), [Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations), [browser WebRTC transport](https://developers.openai.com/api/docs/guides/voice-webrtc). These describe possible next integrations, not features verified in Hina.
