# Phase 2 review gate

## Outcome

Phase 2 is implemented through the offline credential gate. The record-then-process browser/backend cascade, deterministic provider mocks, real-provider adapters, validated TurnPlan stream, speech playback and audio-driven jaw are present. No Azure or Gemini request was made, no credential value was read or logged, and no Android microphone success is claimed.

Phase 2 remains uncommitted on `phase/2-real-voice-brain`. Phase 3 is blocked pending owner review, trusted Android HTTPS setup, a physical microphone test and—only after explicit approval—a maximum three-turn provider smoke test.

## Architecture decisions

- Browser capture uses an explicit tap-to-start/tap-to-process Web Audio recorder, converts mono samples in memory to 16 kHz 16-bit PCM WAV, stops every track and closes nodes/contexts. The deprecated-but-broadly-supported `ScriptProcessorNode` is a Phase 2 compatibility tradeoff; an AudioWorklet is a Phase 3 candidate.
- `/api` is a same-origin Vite proxy to FastAPI. Phase 2 uses HTTP NDJSON for `thinking`, validated `text.delta`, `plan`, `usage` and typed `error`; it does not pre-empt the Phase 3 WebSocket protocol.
- The server validates the complete `AssistantTurnPlan` before emitting display deltas. This delays first visible text versus unsafe partial JSON, but guarantees invalid model cues never reach the avatar.
- `STTProvider`, `LLMProvider` and `TTSProvider` own vendor normalization only. The application owns mode selection, timeout, memory and fallback. Mock is explicit and default; there is no silent paid fallback.
- The official `azure-cognitiveservices-speech` SDK handles raw PCM STT and WAV TTS. `google-genai` uses structured JSON Schema streaming. Vendor imports and credentials remain server-side.
- Session context is an LRU-bounded in-memory store (64 sessions, eight turns each) with an explicit delete endpoint. No database, durable memory or raw microphone retention was added.
- The procedural avatar remains because no local VRM is licence-approved. TTS playback drives a smoothed RMS jaw value; true visemes remain Phase 4.

## Created files

```text
apps/api/.env.example
apps/api/README.md
apps/api/pyproject.toml
apps/api/requirements.txt
apps/api/requirements-dev.txt
apps/api/hinaa_api/__init__.py
apps/api/hinaa_api/audio.py
apps/api/hinaa_api/config.py
apps/api/hinaa_api/errors.py
apps/api/hinaa_api/main.py
apps/api/hinaa_api/memory.py
apps/api/hinaa_api/models.py
apps/api/hinaa_api/services.py
apps/api/hinaa_api/providers/__init__.py
apps/api/hinaa_api/providers/azure_speech.py
apps/api/hinaa_api/providers/base.py
apps/api/hinaa_api/providers/gemini.py
apps/api/hinaa_api/providers/mock.py
apps/api/tests/__init__.py
apps/api/tests/conftest.py
apps/api/tests/fixtures/nepali-30.txt
apps/api/tests/test_api.py
apps/api/tests/test_config.py
apps/api/tests/test_contracts.py
apps/web/src/features/audio/api.ts
apps/web/src/features/audio/microphoneRecorder.test.ts
apps/web/src/features/audio/microphoneRecorder.ts
apps/web/src/features/audio/pcm.test.ts
apps/web/src/features/audio/pcm.ts
apps/web/src/features/audio/useAudioPlayback.ts
apps/web/src/features/providers/backendConversationProvider.test.ts
apps/web/src/features/providers/backendConversationProvider.ts
packages/contracts/schemas/phase-2-stream-event.schema.json
scripts/start-phase2.ps1
docs/24-phase-2-review.md
```

An ignored `apps/api/.env.local` was also created with blank credential fields and mock mode. The ignored `.venv` and `.runtime` directories are local runtime artifacts, not deliverables.

## Modified files

```text
.gitignore
README.md
apps/web/playwright.config.ts
apps/web/src/App.css
apps/web/src/App.test.tsx
apps/web/src/App.tsx
apps/web/src/features/avatar/ProceduralAvatar.tsx
apps/web/src/features/avatar/avatarEngine.ts
apps/web/src/features/companion/useCompanionController.ts
apps/web/src/features/providers/conversationProvider.ts
apps/web/tests/e2e/mobile.spec.ts
apps/web/vite.config.ts
docs/17-roadmap.md
docs/22-requirements-traceability-matrix.md
docs/DEPENDENCY_BASELINE.md
openapi/hinaa-api.yaml
packages/contracts/README.md
```

The existing VRM/ZIP reference assets remain untracked and untouched.

## Configuration and secret boundary

Only the following backend names are recognized for real mode:

```text
AZURE_SPEECH_KEY
AZURE_SPEECH_REGION
GEMINI_API_KEY
GEMINI_MODEL=gemini-3.6-flash
AZURE_SPEECH_FEMALE_VOICE=ne-NP-HemkalaNeural
AZURE_SPEECH_MALE_VOICE=ne-NP-SagarNeural
```

Put credential values only in ignored `apps/api/.env.local`. Do not paste them into chat, use `VITE_*`, commit them, or place them in `apps/api/.env.example`. Missing values leave mock mode healthy and make real mode return `PROVIDER_CONFIGURATION_MISSING`. The production path is managed identity plus Azure Key Vault references; plaintext environment files are local development only.

## Local run and URLs

From the repository root:

```powershell
.\scripts\start-phase2.ps1
```

Current endpoints:

```text
API health: http://127.0.0.1:8000/health/live
PC app (mock/text): http://127.0.0.1:5173/
Android app (mock/text candidate): http://192.168.1.83:5173/
PC trusted HTTPS target: https://127.0.0.1:5173/
Android trusted HTTPS target: https://192.168.1.83:5173/
```

The LAN IP is environment-specific and can change. The launcher prints the current candidate each run.

## Trusted Android HTTPS workflow

Android `getUserMedia` requires a secure, trusted origin. No trust-store change was made automatically and `mkcert` is not installed on this machine. If the owner approves installing and trusting a local development CA:

1. Install `mkcert` from its official distribution using an owner-approved package workflow.
2. Run `mkcert -install` only after explicitly accepting that it modifies the PC trust store.
3. From the repository root generate ignored certificate files that include the current LAN IP:

   ```powershell
   New-Item -ItemType Directory -Force .cert
   mkcert -cert-file .cert/hinaa-dev.pem -key-file .cert/hinaa-dev-key.pem localhost 127.0.0.1 ::1 192.168.1.83
   ```

4. Export/copy only the local CA certificate reported by `mkcert -CAROOT` to the Android device—never copy `rootCA-key.pem` or the site private key. Install it as a user CA only on the dedicated test device, following Android’s visible confirmation flow.
5. Start with `.\scripts\start-phase2.ps1 -Https`, open `https://192.168.1.83:5173/`, confirm the browser shows a trusted connection, then tap **Talk**. Do not bypass certificate warnings.
6. After testing, remove the user CA from Android security settings, run `mkcert -uninstall` if the local CA is no longer needed, and delete the ignored `.cert` files. Regenerate when the LAN IP changes.

The launcher refuses `-Https` when the expected certificate/key files are absent. It never creates or trusts a certificate.

## Validation evidence

Offline/no-paid-call results at the review gate:

```text
Backend Ruff format/lint     PASS
Backend strict mypy         PASS — 13 source files
Backend pytest              PASS — 12 tests
Frontend Prettier/Oxlint    PASS
Frontend TypeScript         PASS
Frontend Vitest             PASS — 19 tests
Mobile/integration E2E      PASS — 10 tests, Pixel 5 + 320×568
Production PWA build        PASS
Frontend pnpm audit         PASS — 0 known vulnerabilities
Backend pip-audit           PASS — 0 known vulnerabilities
Blueprint/contracts         PASS
```

Tests exercise mock provider contracts, PCM format/limits, recorder cleanup, malformed plans, redaction, bounded memory, typed missing configuration, timeout fixtures, backend proxying, offline shell, reduced motion, text-only mode and WebGL loss. They do not fabricate a successful Azure/Gemini result.

## What was and was not tested

Tested: deterministic STT/LLM/TTS mock cascade, final transcript contract, backend text stream, schema validation, synthetic mock WAV playback contract, browser audio conversion/cleanup with mocked media primitives, mobile responsive behavior and safe real-mode rejection without configuration.

Not yet tested: physical microphone capture, Android permission UI, trusted Android HTTPS, actual Nepali STT accuracy, actual Hemkala/Sagar audio, Gemini response quality, provider quota/latency/cost, acoustic echo, noisy-room behavior or a full paid cascade. Therefore “real voice works” and latency claims are intentionally withheld. Only mock/development latency is displayed in the UI.

### Live-provider smoke-test preflight — 2026-07-30

The owner approved at most three short, non-sensitive real-provider turns against the intended Azure Speech Free F0 resource. `git check-ignore -v -- apps/api/.env.local` confirmed the credential file is ignored by `.gitignore:2:.env.*`. No credential value was opened, printed, copied, logged or summarized.

The existing FastAPI and Vite applications started successfully. Backend liveness returned `ok` at version `0.2.0`, readiness returned HTTP 200 in mock mode, the frontend returned HTTP 200, and the same-origin services were reachable. Because the API process predated the environment-file update, two verified HINAA Uvicorn processes were stopped and restarted without inspecting the file.

After restart, safe `/v1/providers` metadata still reported `azure-speech=unavailable` and `gemini=unavailable`; mock remained `healthy`. Testing stopped before the first provider request. Result: **0/3 live turns used, zero real recordings, zero measured live latency, and no quota/cost indication because no provider call occurred**. The configured resource tier remains owner-intended F0 and cannot be independently proven from a Speech key or this safe status endpoint. Mock mode remains active.

A second owner-requested preflight repeated `git check-ignore`, performed another clean restart of only the verified HINAA Uvicorn processes, and rechecked API/frontend health. The result was unchanged: mock `healthy`, Azure Speech `unavailable`, Gemini `unavailable`, and **0/3 live turns used**. No provider traffic or resource modification occurred during either attempt.

### Credential-recognition diagnosis — 2026-07-30

A credential-recognition-only diagnostic was explicitly authorized, with provider calls forbidden. The exact `apps/api/.env.local` file exists, `.env.local.txt` does not, and `git check-ignore -v` again confirmed `.gitignore:2:.env.*`. A metadata-only parser returned `PRESENT/NONEMPTY` for `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, and `GEMINI_API_KEY`; it found valid UTF-8 without BOM, no invalid lines, no required-name duplicates, no required placeholders, and no `VITE_` credential names. The configured Gemini model and Azure voice names are legitimate optional non-secret settings. The tracked root `.env.example` was unmodified and contained placeholders/names only, with no tracked-secret risk detected. No value was displayed, logged, copied or summarized.

The configuration path was not defective: `ENV_FILE` resolves from `config.py` to the absolute repository path `apps/api/.env.local`, independent of terminal working directory, and a fresh isolated `Settings()` recognized all three settings. The actual cause was process lifecycle: an orphaned Uvicorn `--reload` spawn child continued serving settings cached before the file update even though its reloader parent no longer existed. Normal health-based startup therefore reused stale configuration.

The verified orphan was stopped, and `scripts/start-phase2.ps1` was changed to launch a single Uvicorn process without `--reload`. After the fresh start, safe local metadata reported `mock=healthy`, `azure-speech=healthy`, and `gemini=healthy`; backend liveness was `ok` at `0.2.0`, frontend connectivity returned HTTP 200, and readiness remained `mode=mock`. These provider states prove configuration presence only and did not contact Azure or Gemini. Result remains **0/3 live turns used**, no recordings, no latency/cost/quota measurement, no Azure resource change, and no live-test authorization carried forward without fresh owner approval.

Before resuming the same capped authorization, verify locally that the ignored file uses exactly `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, and `GEMINI_API_KEY`, with nonempty values and no `VITE_` prefix. Do not provide the values in chat. A fresh backend restart and safe provider-state check must pass before any of the three turns.

## Remaining risks and Phase 3 recommendation

- Physical Android secure-context and audio-driver behavior remains the largest Phase 2 gate.
- Azure/Gemini catalog IDs were verified in official documentation, but account region/quota/model access can still differ.
- `ScriptProcessorNode` is deprecated; move capture to AudioWorklet in Phase 3 before continuous streaming.
- HTTP NDJSON validates first and streams second, so first-text latency is not a provider-token measurement.
- Mock tone audio proves playback mechanics, not voice quality. Real voice requires owner-approved provider testing.
- Vite dev HTTPS and user-installed local CAs are development-only. A deployed pilot must use publicly trusted TLS.
- The optional Vite/Rolldown `@emnapi` alpha peer mismatch remains documented; builds pass without adding alpha peers.
- Current backend tests emit upstream deprecation warnings for FastAPI/Starlette's transition from `httpx` to `httpx2` and a Python 3.17-targeted internal typing alias in `google-genai`. They do not affect Python 3.14 runtime behavior; recheck on the next stable dependency refresh.

Phase 3 should add the versioned WebSocket envelope, partial STT, bounded audio chunks, shared cancellation generations, first-audio streaming and measured local barge-in. It must preserve the current REST/mock fallback and cannot begin until this gate is approved.

## Review gate

After trusted-device and, if authorized, capped provider testing, approve the next phase with exactly:

```text
APPROVE HINAA PHASE 2. START HINAA PHASE 3 — LIVE STREAMING AND INTERRUPTION.
```
