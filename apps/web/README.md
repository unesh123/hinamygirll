# HINAA web — Phase 3

Mobile-first companion playground with AudioWorklet capture, local VAD, realtime WebSocket events, ordered audio playback and preserved mock/REST/text fallbacks. Credentials never enter the frontend, and the unapproved local VRM remains quarantined.

## Commands

```powershell
pnpm install
pnpm dev --host 0.0.0.0
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
pnpm build
```

Use PC loopback for microphone review. A LAN Android microphone test requires a trusted HTTPS origin. The procedural avatar is intentionally replaceable by a licensed VRM adapter after the asset gate.

**Start Live Conversation** keeps a visible microphone indicator, detects speech and commits after bounded trailing silence. **Push-to-talk**, text, and **Demo without mic** remain fallback paths. Development calibration controls do not generate a provider sample without separate approval.
