# HINAA blueprint

HINAA is a proposed mobile-first, multilingual Nepali 3D companion and personal assistant. The approved Phase 1 mock companion is checkpointed. **Phase 2 record-then-process voice and chat** now has an offline-tested FastAPI backend, browser microphone pipeline, provider interfaces and safe mock cascade; real provider verification is stopped at the credential/approval gate.

## Decision summary

- Final-year MVP: installable React/TypeScript/Vite PWA, two selectable VRM companions, text and tap-to-talk, streaming transcription/text/audio, barge-in, bounded emotion/motion, explicit memory, mock mode, and mobile degradation.
- Architecture: one FastAPI modular monolith, PostgreSQL + pgvector, a provider router, WebSocket application events, optional provider-direct WebRTC, and browser-side Three.js/React Three Fiber/`@pixiv/three-vrm` rendering.
- Default benchmark candidate: Gemini Developer API for conversation and Azure Speech `ne-NP` for STT/TTS. Provider and model identifiers remain configuration, never code assumptions.
- Safety: no autonomous device control, background surveillance, payments, unrestricted tools, or BYOK execution in the MVP.
- Local assets already present are quarantined until their exact embedded VRM licences, provenance, and redistribution terms are recorded in [ASSET_LICENSES.md](docs/ASSET_LICENSES.md).

## Blueprint index

Start with [executive summary](docs/00-executive-summary.md), [scope](docs/02-scope-and-requirements.md), [architecture](docs/04-system-architecture.md), [roadmap](docs/17-roadmap.md), and [traceability matrix](docs/22-requirements-traceability-matrix.md). Technical contracts are in [OpenAPI](openapi/hinaa-api.yaml), [JSON Schemas](packages/contracts/schemas/), [provider ports](packages/provider-sdk/README.md), [prompt specifications](docs/prompts/), and the dated [dependency baseline](docs/DEPENDENCY_BASELINE.md).

## Repository boundary

```text
docs/                  architecture, ADRs, research and operations
docs/diagrams/         Mermaid source
docs/prompts/          layered prompt specifications (not production prompts)
openapi/               HTTP API contract
packages/contracts/    versioned JSON Schemas
packages/provider-sdk/ provider-independent interface specification
apps/web/               Phase 1 React PWA and deterministic mock experience
apps/api/               Phase 2 FastAPI cascade, provider ports and mocks
```

The existing ZIP, VRM and Unity reference material has not been moved, modified, or approved for shipping.

## Phase 0 validation

From the repository root:

```powershell
python scripts/validate_blueprint.py
```

The validator checks JSON syntax/schema examples, OpenAPI YAML structure, required documents, local Markdown links, protocol event coverage, and Mermaid source presence.

## Phase 2 local run

From the repository root:

```powershell
.\scripts\start-phase2.ps1
```

Open `http://127.0.0.1:5173/` on the PC for mock/text review. The current LAN candidate is `http://192.168.1.83:5173/`; Android microphone access requires the trusted HTTPS workflow in [Phase 2 review](docs/24-phase-2-review.md). The primary mic button requests permission only when tapped; **Demo without mic** preserves the Phase 1 simulator.

Real credentials belong only in ignored `apps/api/.env.local` using `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, and `GEMINI_API_KEY`. Never use a `VITE_*` secret. Mock mode requires no credentials and makes no paid calls. Real calls remain unverified until the owner adds backend credentials and explicitly approves a maximum three-turn test.
