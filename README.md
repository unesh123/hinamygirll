# HINAA blueprint

HINAA is a mobile-first, multilingual Nepali AI companion and personal assistant. Phase 3 live streaming and hands-free conversation feature ElevenLabs TTS (Simran voice `TRnaQb7q41oL7sV0w6Bu`), ElevenLabs Scribe v2 STT architecture, Google Gemini Brain cascade, a unified `HinaaExperienceState` state machine, 50-scene `MotionScene` system, `PlaybackLeakGuard` self-echo protection, and barge-in audio interruption; real streaming microphone verification remains at the owner-gated review scripts.

## Decision summary

- Final-year MVP: installable React/TypeScript/Vite PWA, selectable companions (Hinaa & Hiro), text chat and continuous hands-free voice sessions, streaming transcription/text/audio, barge-in, bounded voice performance planner, explicit memory, mock mode, and mobile degradation.
- Architecture: FastAPI modular monolith backend, PostgreSQL + pgvector, ElevenLabs provider integration (server-side keys only), WebSocket realtime events, and procedural web visual core.
- Default benchmark candidate: Gemini Developer API for conversation and Azure Speech `ne-NP` for STT/TTS. Provider and model identifiers remain configuration, never code assumptions.
- Safety: no autonomous device control, background surveillance, payments, unrestricted tools, or BYOK execution in the MVP.
- Local assets already present are quarantined until their exact embedded VRM licences, provenance, and redistribution terms are recorded in [ASSET_LICENSES.md](docs/ASSET_LICENSES.md).

## Blueprint index

Start with [master AI blueprint](docs/HINA-MASTER-BLUEPRINT-FOR-AI.md), [executive summary](docs/00-executive-summary.md), [scope](docs/02-scope-and-requirements.md), [architecture](docs/04-system-architecture.md), [roadmap](docs/17-roadmap.md), and [traceability matrix](docs/22-requirements-traceability-matrix.md). Technical contracts are in [OpenAPI](openapi/hinaa-api.yaml), [JSON Schemas](packages/contracts/schemas/), [provider ports](packages/provider-sdk/README.md), [prompt specifications](docs/prompts/), and the dated [dependency baseline](docs/DEPENDENCY_BASELINE.md).

Progress reports: [26 Tier A](docs/26-tier-a-conversation-brain-implementation.md) · [27 verify](docs/27-tier-a-verification-report.md) · [28 providers](docs/28-real-provider-evaluation.md) · [29 presence](docs/29-phase-4-presence-implementation.md) · [30 memory](docs/30-phase-5-memory-architecture.md) · [39 readiness](docs/39-production-readiness-audit.md).

## Repository boundary

```text
docs/                  architecture, ADRs, research and operations
docs/diagrams/         Mermaid source
docs/prompts/          layered prompt specifications (not production prompts)
openapi/               HTTP API contract
packages/contracts/    versioned JSON Schemas
packages/provider-sdk/ provider-independent interface specification
apps/web/               Phase 3 React PWA, realtime audio client and fallbacks
apps/api/               Phase 3 FastAPI realtime gateway, cascade and mocks
```

The existing ZIP, VRM and Unity reference material has not been moved, modified, or approved for shipping.

## Phase 0 validation

From the repository root:

```powershell
python scripts/validate_blueprint.py
```

The validator checks JSON syntax/schema examples, OpenAPI YAML structure, required documents, local Markdown links, protocol event coverage, and Mermaid source presence.

## Phase 3 local run

From the repository root:

```powershell
.\scripts\start-phase3.ps1
```

Open `http://127.0.0.1:5173/` on the PC for mock/realtime review. **Start Live Conversation** requests microphone permission, keeps a visible indicator active and automatically detects speech; push-to-talk, text, and deterministic mock controls remain available. Android microphone use over LAN requires trusted HTTPS as documented in [Phase 3 review](docs/25-phase-3-review.md); do not use insecure LAN HTTP or bypass certificate warnings.

Real credentials belong only in ignored `apps/api/.env.local` using `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, and `GEMINI_API_KEY`. Never use a `VITE_*` secret. Mock mode requires no credentials and makes no paid calls. Hemkala and Sagar are standard Azure Nepali neural voices—not custom anime identities. A unique Hinaa voice requires a licensed, consenting voice actor or approved custom-voice dataset. Real Phase 3 calls remain blocked until a new, explicit capped streaming-test approval.
