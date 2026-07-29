# HINAA web — Phase 1

Mobile-first deterministic mock companion playground. It uses no microphone capture, credentials, external AI provider or unapproved VRM.

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

Open the LAN URL printed by Vite on an Android browser. The procedural avatar is an implementation of the avatar-engine interface and is intentionally replaceable by a licensed VRM adapter in a later approved phase.

Use `/error` as a text message to test the safe error state. The “Try voice” control simulates partial transcription and clearly does not request microphone permission.
