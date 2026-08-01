# Dependency baseline

## Purpose

Record current stable candidates without pretending an untested set is a production lockfile.

## Decision

Registry `latest` values checked 2026-07-30:

| Area | Package | Candidate |
|---|---|---:|
| UI | `react`, `react-dom` | 19.2.8 (React latest major/minor is 19.2) |
| build | `vite` | 8.1.5 |
| language | `typescript` | 7.0.2 |
| tokens/utilities | `tailwindcss` | 4.3.3 (optional; semantic CSS tokens remain canonical) |
| 3D | `three` | 0.185.1 |
| React 3D | `@react-three/fiber` | 9.6.1 |
| VRM | `@pixiv/three-vrm` | 3.5.5 |
| PWA | `vite-plugin-pwa` | 1.3.0 |
| client validation | `zod` | 4.4.3 |
| browser tests | `@playwright/test` | 1.62.0 |
| API | `fastapi` | 0.141.1 |
| contracts | `pydantic` | 2.13.4 |
| ORM | `sqlalchemy` | 2.0.51 |
| migrations | `alembic` | 1.18.5 |
| PostgreSQL driver | `asyncpg` | 0.31.0 |
| vector integration | `pgvector` (Python) | 0.5.0 |
| backend tests | `pytest` | 9.1.1 |
| API server | `uvicorn` | 0.52.0 |
| settings | `pydantic-settings` | 2.14.2 |
| multipart | `python-multipart` | 0.0.32 |
| Azure speech | `azure-cognitiveservices-speech` | 1.51.1 |
| Gemini | `google-genai` | 2.15.0 |
| Python lint/type | `ruff`, `mypy` | 0.16.0, 2.3.0 |
| Python audit | `pip-audit` | 2.10.1 |

Phase 1–3 reproducibility baseline: Node `v24.13.1`, `pnpm@11.7.0` (pinned in `apps/web/package.json`), Corepack `0.34.6`, and Python `3.14.4` on Windows 11. Phase 3 adds no dependency: browser AudioWorklet/WebSocket/Web Audio APIs and FastAPI/Starlette WebSockets use the existing pinned runtime. Exact direct backend dependencies remain pinned in `apps/api/requirements*.txt`. The official Microsoft Speech SDK supports both TTS and the continuous raw PCM push stream used here; no separate transcription preview package was added.

Phase 1 must create lockfiles, check Node/Python support ranges and peer dependencies, run a minimal React/R3F/three-vrm/Vite compatibility spike, and pin exact versions. “Latest” is not automatically safest; patch security advisories and compatibility evidence take priority. PostgreSQL server/pgvector extension versions are selected from the supported Docker/managed-platform matrix then, not inferred from the Python package.

## Alternatives considered

Hard-coding ranges now would age before implementation; leaving versions undocumented violates reproducibility.

## Reasoning

A dated candidate table satisfies research traceability while deferring the actual lockfile to implementation evidence.

## Risks

TypeScript 7, Vite 8, Tailwind 4 or React ecosystem peers may expose incompatibilities. Phase 1 may choose the newest supported prior major/minor and record an ADR amendment.

## Acceptance criteria

- Phase 1 lockfiles resolve without peer warnings and pass build/test/security scan.
- Every downgrade has a compatibility/security reason.
- Provider SDK/model versions remain configuration and separate from application dependency versions.

## Sources verified 2026-07-30

[React versions](https://react.dev/versions), [Vite releases](https://vite.dev/releases), [npm package registry](https://www.npmjs.com/), [PyPI package index](https://pypi.org/), [`@pixiv/three-vrm`](https://www.npmjs.com/package/@pixiv/three-vrm).
