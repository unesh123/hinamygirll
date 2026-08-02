# 46 — Production outage behavior (local live honesty)

Local live mode with `providerMode=real`:

- Never silently substitutes mock LLM/STT/TTS answers.
- Gemini unavailable → provider unavailable error UI.
- Azure STT failure → typed live-provider / text fallback remains available.
- Azure TTS failure → show generated text and mark voice unavailable; do not
  pretend audio played.
- Reconnect uses bounded client backoff; no infinite loops.
- Do not replay completed old audio after reconnect.
- Do not send duplicate user turns.
- Mock remains for tests, diagnostics, and explicit mock mode only.

This document does **not** claim production multi-region availability.
