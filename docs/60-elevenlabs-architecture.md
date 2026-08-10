# HINAA Document 60: ElevenLabs TTS Provider Architecture & Security Boundaries

## Architectural Overview
ElevenLabs integration in HINAA is designed as a backend-isolated, owner-gated TTS provider (`ElevenLabsHTTPStreamingProvider` & `ElevenLabsWebSocketStreamingProvider`).

## Security & Key Isolation Rules
1. **Zero Client-Side Exposure**: `ELEVENLABS_API_KEY` is loaded exclusively inside Python `hinaa_api.config.Settings`. No `VITE_ELEVENLABS_` environment variables exist.
2. **Sanitized Error Pipeline**: Upstream ElevenLabs API errors (e.g. 401, 403, 429) are mapped to `ElevenLabsStatus` enum values (`authenticationFailed`, `quotaFailed`, `voiceUnsupported`, `modelUnsupported`, `timeout`). Raw credentials or vendor error dumps are stripped before reaching the client.
3. **Key Masking**: Any diagnostic output or log preview masks the API key as `key_abcd...xxxx`.

## Provider Modes
- **Mode A (HTTP Streaming)**: Uses `/v1/text-to-speech/{voice_id}/stream` with chunked byte streaming via `httpx.AsyncClient`.
- **Mode B (WebSocket Streaming)**: Architecture prepared for `/v1/text-to-speech/{voice_id}/stream-input`. Requires independent benchmarking against Mode A.

## Runtime Status Lifecycle
Provider availability is NOT inferred merely from key presence:
- `configured`: Environment variables present.
- `authenticationUntested`: Key present, zero runtime calls made.
- `available`: Verified by successful owner-gated smoke test.
- `unavailable`: Key or configuration missing.
- `authenticationFailed`: Upstream 401/403.
- `quotaFailed`: Upstream 429.
