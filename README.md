# HINAA blueprint

HINAA is a proposed mobile-first, multilingual Nepali 3D companion and personal assistant. Phase 2 is checkpointed. **Phase 3 live streaming and interruption** now has an offline-tested WebSocket protocol, AudioWorklet capture, local VAD, partial/final events, streamed text, ordered phrase audio and generation-based barge-in; real streaming-provider verification remains at the separate user-assisted review gate.

## Decision summary

- Final-year MVP: installable React/TypeScript/Vite PWA, two selectable VRM companions, text and tap-to-talk, streaming transcription/text/audio, barge-in, bounded emotion/motion, explicit memory, mock mode, and mobile degradation.
- Architecture: one FastAPI modular monolith, PostgreSQL + pgvector, a provider router, WebSocket application events, optional provider-direct WebRTC, and browser-side Three.js/React Three Fiber/`@pixiv/three-vrm` rendering.
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
