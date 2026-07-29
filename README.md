# HINAA blueprint

HINAA is a proposed mobile-first, multilingual Nepali 3D companion and personal assistant. This repository currently contains **Phase 0 architecture and interface specifications only**. Production implementation is intentionally blocked until the owner types `START HINAA PHASE 1`.

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
```

The existing ZIP, VRM and Unity reference material has not been moved, modified, or approved for shipping.

## Phase 0 validation

From the repository root:

```powershell
python scripts/validate_blueprint.py
```

The validator checks JSON syntax/schema examples, OpenAPI YAML structure, required documents, local Markdown links, protocol event coverage, and Mermaid source presence.

## Approval gate and exact Phase 1 command

Do not run this yet. After explicit approval, the recommended command is:

```powershell
pnpm create vite@latest apps/web --template react-ts
```

This first command scaffolds only the web client. Dependency versions must be pinned from the official registries on that implementation date.
