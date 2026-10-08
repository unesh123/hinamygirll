# ElevenLabs voice repair — 7 October 2026

The configured Hina voice resolves through ElevenLabs to **Aisha – Sweet Expressive Girlfriend** (voice ID `WUgmmuDCpFXQ4z0NUUYX`). The account accepted synthesis; no new API key or voice purchase was needed for the checks.

## Repairs

- The top-bar voice menu now renders in a body portal outside the clipped header. It stays within the viewport, scrolls, supports keyboard navigation/Escape, and returns focus after selecting an engine.
- File-backed SQLite now uses separate pooled connections for concurrent requests. The previous shared StaticPool connection could cause authentication database errors during overlapping speech requests. In-memory tests retain their shared database.
- Playback reports blocked audio contexts and decoder failures. Invalid compressed audio is no longer interpreted as raw PCM noise.
- Temporary ElevenLabs rate limits and server errors receive bounded retries. Authentication, parameter rejection and exhausted account credits fail without pointless retries; partially received audio is never restarted automatically.

## Verification

- Real ElevenLabs voice lookup: HTTP 200; configured voice name confirmed.
- Real direct synthesis: HTTP 200, audio/mpeg, 39,750 bytes, 886 ms for a short sample.
- Configured WebSocket provider: 98,082 audio bytes, 1,253 ms.
- Hina service synthesis with Auto and explicit ElevenLabs: provider elevenlabs, 89,164 bytes each; 1,158 ms and 1,035 ms respectively. These are synthesis times, not measured audible browser onset.
- 67 backend checks passed (voice, WebSocket, fallback, progressive speech, Clerk auth, database concurrency and migrations).
- Two additional retry regression cases passed within a 24-test ElevenLabs unit suite.
- 24 frontend checks passed; two existing todo cases remain. Production typecheck/build passed.

## Browser acceptance

The saved Hina browser-access block still prevents an authenticated live UI/playback check. Actual audible playback on the owner device is unverified. A generated sample is saved privately in `.runtime/live/hina-aisha-voice-check.mp3`.

After deployment, refresh Hina, open the microphone/voice selector, choose ElevenLabs (Aisha), ensure audio is unmuted, and send a short message. Auto also selects the configured ElevenLabs voice. If browser audio is blocked, tap an audio control to enable playback. Provider fallback is labeled when the original service refuses a request.
