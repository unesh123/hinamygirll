# 42 — Realtime latency architecture

## Pipeline (local live)

```
Microphone → AudioWorklet PCM → Local TurnTakingController/VAD
→ WebSocket /v1/realtime → Azure continuous STT
→ Gemini streamed text → stable phrase detector
→ Azure phrase TTS → ordered playback
→ Procedural expression + amplitude jaw
→ automatic return to listening
```

## Milestone clock

Client `LatencyClock` marks monotonic milestones when observed:

`live_session_started`, `microphone_ready`, `speech_started`, `first_stt_partial`,
`speech_ended`, `turn_committed`, `stt_final`, `llm_request_started`,
`first_text_delta`, `first_stable_phrase`, `tts_request_started`,
`first_audio_chunk`, `playback_started`, `final_text`, `final_audio`,
`turn_completed`, `interruption_detected`, `playback_stopped`,
`server_cancel_acknowledged`.

## Optimization principles

- Reuse WebSocket and avoid SDK init per turn.
- Stream text; start TTS on first stable phrase.
- Bound TTS phrase queue (server max 8 phrases).
- Cancel queued audio/performance on barge-in.
- Keep animation off the critical provider path.
- Do not invent 0.01-second end-to-end cloud claims.
- Separate mock timings from real provider timings.

## Not verified until owner-gated real evaluation

First-token and first-audio latency under Gemini + Azure on this machine.
