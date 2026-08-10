# HINAA MASTER BLUEPRINT FOR AI & MULTILINGUAL VOICE ARCHITECTURE

## 1. System Core
- **Brain**: Google Gemini Flash 3.6 / OpenAI Codex / Agent Router
- **STT**: ElevenLabs Scribe v2 Realtime (Nepali, Hindi, English) / Local Whisper STT
- **TTS**: ElevenLabs HTTP/WebSocket Streaming (Simran `TRnaQb7q41oL7sV0w6Bu`)
- **Echo & Barge-In**: `PlaybackLeakGuard` + Browser AudioWorklet PCM
- **Voice Performance**: `VoicePerformancePlanner` (Semantic Mode Allowlist)
- **Lip Sync**: Alignment Viseme Approximation (`open`, `wide`, `rounded`, `neutral`)

## 2. Security & Key Isolation
- `ELEVENLABS_API_KEY` is strictly server-side in `apps/api/.env.local`. Zero keys in frontend bundles.

## 3. Owner-Gated Test Scripts
- `scripts/test_elevenlabs_tts.py`
- `scripts/test_elevenlabs_stt_realtime.py`
- `scripts/test_hinaa_elevenlabs_live_turn.py`
