# HINAA / Hina — Master Blueprint for AI Agents

**Purpose of this document:** Give any AI agent full context to understand, continue, or improve HINAA without guessing. Read this first, then open linked docs before changing code.

**Product names:** Project folder `HINAMYGIRL`. Product **HINAA**. Companions: **Hinaa** (female) and **Hiro** (male). User often says “Hina” = Hinaa companion + whole system.

**Date context:** Phase 0–3 offline work complete as of 2026-07-30. Branch for Phase 3: `phase/3-live-streaming`. Phase 2 checkpoint: `d8653ef`. Phase 3 often uncommitted. Do not begin Phase 4, commit, or push unless the owner explicitly asks.

---

## 1. One-sentence product

HINAA is a **mobile-first, multilingual Nepali 3D companion + personal assistant** PWA: talk or type → get a warm, safe, code-switching reply → hear Nepali TTS → see synchronized avatar performance — with mock/offline fallback always available.

---

## 2. North star (“perfect Hina”)

A high-level advanced Hina means:

| Pillar | Perfect means |
|---|---|
| **Conversation** | Natural Nepali/English/Hindi mix; remembers you; consistent personality; not robotic 1–2 lines only |
| **Brain** | Layered prompts + structured `AssistantTurnPlan`; optional tools later; multi-turn coherence |
| **Memory** | Explicit long-term memory with consent; summaries; privacy delete |
| **Voice** | Low-latency STT/TTS; barge-in; distinctive voice identity (later: custom, not stock Azure) |
| **Presence** | Licensed VRM, emotions, gestures, lips/visemes synced to speech |
| **Safety** | Explicitly AI; no consciousness claims; no jealousy/dependency; no autonomous device control |
| **Reliability** | Mock mode, text-only, degraded avatar always work |

**MVP intentionally is NOT:** unbounded roleplay, AGI, surveillance, payments, unrestricted tools, or cloned celebrity/anime voices.

---

## 3. Current status (honest)

### Done / working (offline + mock)

| Area | Status |
|---|---|
| Phase 0 full docs, ADRs, contracts, validator | ✅ |
| React 19 + Vite 8 PWA (installable, SW) | ✅ |
| Companion switch Hinaa / Hiro | ✅ |
| States: idle, listening, thinking, speaking, interrupted, error | ✅ |
| Mock conversation (text + demo without mic) | ✅ |
| FastAPI modular monolith + REST cascade | ✅ |
| Azure STT/TTS + Gemini adapters (lazy, code present) | ✅ adapters |
| Session memory (last N turns, in-process RAM) | ✅ ephemeral |
| Phase 3 WebSocket `/v1/realtime` protocol 1.0 | ✅ offline tested |
| AudioWorklet PCM, local VAD, barge-in by generation | ✅ |
| Procedural CSS avatar (breath/blink/gaze/jaw energy) | ✅ |
| Automated tests (API, contracts, Vitest, Playwright) | ✅ |

### Not done / gated / stubbed

| Area | Status | Blocker |
|---|---|---|
| Real Azure continuous STT + real Gemini + real TTS in live path | 🔒 Gated | Owner must approve capped paid streaming test |
| Layered personality prompt assembly from `docs/prompts/` | ✅ Tier A runtime wired | See `apps/api/hinaa_api/prompts/` + `docs/26`/`27` |
| Explicit memory CRUD + privacy API | ✅ Offline Phase 5 scaffold | SQLite/dev-auth; Postgres URL ready; RLS/OIDC incomplete (`docs/30`/`31`) |
| Conversation summaries / remember-forget | ✅ Partial | Summaries on message cadence; remember/forget/export/delete-all APIs |
| VRM / Three.js / `@pixiv/three-vrm` | ❌ | Assets quarantined (`ASSET_LICENSES.md`) |
| Performance scheduler + amplitude lips | ✅ Phase 4 offline | Procedural only; no visemes/VRM (`docs/29`) |
| Auth, multi-user, RLS, privacy dashboard | ⚠️ Partial | Dev auth + privacy panel/API; OIDC/RLS not production-ready |
| Tools / vision / image gen | ❌ Post-MVP | Disabled by design in MVP |
| Custom unique Hina voice | ❌ Out of scope now | Needs licensed voice actor / dataset |
| Android mic over LAN | ⚠️ | Needs trusted HTTPS |
| Eval suite / Nepali quality benchmarks with real calls | ❌ Phase 6 | 0 live provider calls claimed in Phase 3 review |
| Phase 3 git commit / push | ⚠️ | Owner decision |

**Bottom line:** Pipeline is real. Tier A layered conversation brain is now wired offline (distinct companions, multilingual policy, bounded personality, schema fallback). Durable memory and VRM presence are still missing. Real Gemini/Azure conversational quality remains owner-gated and unmeasured.

---

## 4. Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite 8, Zod 4, vite-plugin-pwa, Vitest, Playwright |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| LLM | Gemini via `google-genai` (default model config, e.g. `gemini-3.6-flash`) — **no OpenAI/Claude in code** |
| Speech | Azure Cognitive Services Speech — `ne-NP-HemkalaNeural` (Hinaa), `ne-NP-SagarNeural` (Hiro) |
| Realtime | WebSocket app protocol + browser AudioWorklet |
| Avatar planned | Three.js / R3F / `@pixiv/three-vrm` — **not installed** |
| DB planned | PostgreSQL + pgvector — **not implemented** |
| Package managers | pnpm (web), pip (api) |

Secrets: only in ignored `apps/api/.env.local` — `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `GEMINI_API_KEY`. Never `VITE_*` secrets.

---

## 5. Repository map

```text
HINAMYGIRL/
├── README.md
├── .env.example
├── apps/
│   ├── api/hinaa_api/          # FastAPI: main, services, realtime, memory, providers
│   └── web/src/                # PWA: App, features/audio|avatar|companion|providers
├── packages/
│   ├── contracts/schemas/      # AssistantTurnPlan, realtime, stream events
│   └── provider-sdk/           # Interface SPEC only (not executable SDK)
├── docs/                       # Architecture, ADRs, prompts, phase reviews, THIS file
├── openapi/hinaa-api.yaml
├── scripts/                    # validate_blueprint.py, start-phase2/3.ps1
└── [VRM/ZIP/Unity]             # QUARANTINED — do not load/ship without licence sign-off
```

### Must-read docs (in order)

1. `docs/00-executive-summary.md`
2. `docs/01-product-vision.md`
3. `docs/02-scope-and-requirements.md`
4. `docs/04-system-architecture.md`
5. `docs/05-realtime-event-protocol.md`
6. `docs/09-memory-and-database.md`
7. `docs/11-prompt-and-personality-architecture.md`
8. `docs/17-roadmap.md`
9. `docs/25-phase-3-review.md` (current gate)
10. `docs/prompts/*` (layered prompt specs — not wired to production yet)
11. `docs/adr/*` (decisions)
12. `docs/ASSET_LICENSES.md` (avatar gate)

### Key code files

| Path | Role |
|---|---|
| `apps/api/hinaa_api/main.py` | REST + WS entry |
| `apps/api/hinaa_api/services.py` | Turn orchestration / router |
| `apps/api/hinaa_api/realtime.py` | Live STT→LLM→TTS cascade |
| `apps/api/hinaa_api/providers/gemini.py` | Gemini (thin prompts today) |
| `apps/api/hinaa_api/providers/azure_speech.py` | Azure STT/TTS |
| `apps/api/hinaa_api/providers/mock.py` | Deterministic offline |
| `apps/api/hinaa_api/memory.py` | In-process session history |
| `apps/api/hinaa_api/config.py` | Env/config |
| `apps/web/src/features/audio/useLiveConversation.ts` | Live mic/VAD/WS client |
| `apps/web/src/features/avatar/*` | Procedural avatar engine |
| `apps/web/src/contracts/assistantTurnPlan.ts` | Client Zod TurnPlan |

---

## 6. Conversation architecture (how she thinks/talks)

### Core object: `AssistantTurnPlan`

Server-validated structured plan (JSON Schema + Pydantic/Zod). Model must not pick bones, files, or tools freely. Invalid plan → schema retry once → safe neutral fallback.

Includes spoken text + bounded emotion/gesture/performance cues for the avatar engine.

### Path A — REST cascade (Phase 2)

```text
User text or recorded WAV
  → STT (optional)
  → Gemini/Mock create_plan → AssistantTurnPlan JSON
  → SessionMemory.append
  → NDJSON stream: thinking → text.delta* → plan → usage
  → TTS WAV → playback + jaw energy → procedural avatar cues
```

### Path B — Live WebSocket (Phase 3)

```text
Mic → AudioWorklet 16 kHz PCM + local VAD (~700 ms silence commit)
  → WS /v1/realtime protocol 1.0
  → Azure continuous STT (or mock partial/final)
  → Gemini streamed short text (sanitized) + server builds TurnPlan
  → phrase-split TTS → ordered audio chunks
  → barge-in: local stop → interrupt → generation++ (stale ignored)
```

**Ownership:** Server owns sequence, cancellation, validation. Client owns immediate audio stop and render scheduling.

**Quality caveat:** Live Gemini is capped to short replies; emotion/gestures often hardcoded after text — not full layered personality yet.

---

## 7. Personality & prompt system (designed vs implemented)

### Designed (11-layer assembly — `docs/11-prompt-and-personality-architecture.md`)

1. Immutable safety/privacy  
2. Product behavior + AI identity transparency  
3. Selected companion identity (Hinaa vs Hiro)  
4. Nepali/mixed-language style  
5. Bounded user personality sliders (affection, sass, energy, humor, proactivity — clamped)  
6. Bounded mood snapshot  
7. Conversation context  
8. Approved retrieved memories with IDs  
9. Untrusted vision/retrieval/tool data in delimited blocks  
10. Tool policy (disabled in MVP)  
11. Response JSON schema + allowlists  

Specs: `docs/prompts/female-companion.md`, `male-companion.md`, `nepali-response-style.md`, `emotion-performance-planner.md`, `memory-candidate-extractor.md`, `conversation-summarizer.md`, etc.

### Implemented today

Short `SYSTEM_PROMPT` / `LIVE_SYSTEM_PROMPT` in `apps/api/hinaa_api/providers/gemini.py`. Companion ID is a string; rich layered assembly is **not wired**.

---

## 8. Memory model

| Layer | Status |
|---|---|
| Current turn | ✅ |
| Ephemeral session (e.g. last 8 turns, ~64 sessions, RAM) | ✅ |
| Conversation summaries | ❌ Spec |
| Explicit long-term (“remember this”) + consent | ❌ Spec / ADR-007 |
| Semantic retrieval (pgvector) | ❌ Spec |
| Privacy dashboard / delete-all | ❌ Phase 5 |
| Auth / RLS multi-user | ❌ Phase 5 |

Design target: `docs/09-memory-and-database.md`, ADR-005, ADR-007.

---

## 9. Avatar / presence

- Interface supports `"vrm"` kind; only `ProceduralAvatarEngine` exists.
- Local VRMs quarantined — do not load until `ASSET_LICENSES.md` is complete and owner approves.
- Jaw = audio amplitude, not visemes.
- Phase 4: TurnPlan performance clock, emotion/gesture layers, lips, 5–10 polished motions.

---

## 10. Safety non-negotiables

- She is **explicitly artificial**; no consciousness / dependency / jealousy / exclusivity claims.
- No autonomous device control, background surveillance, payments, unrestricted tools, BYOK execution in MVP.
- Secrets never in client bundles or git.
- Schema validation rejects extra properties / out-of-allowlist cues.
- Hostile injection in memory/vision/tools must be ignored (test corpus planned).

---

## 11. Roadmap phases

| Phase | Theme | Status |
|---|---|---|
| 0 | Blueprint | ✅ Done |
| 1 | PWA + mock + procedural avatar | ✅ Done (offline) |
| 2 | FastAPI + Azure/Gemini adapters + mic REST | ✅ Offline; credential gate |
| 3 | Live WS, VAD, barge-in, streaming | ✅ Offline; **real streaming gate open** |
| 4 | Performance clock, motions, lips | ✅ Offline procedural scheduler; VRM/visemes blocked |
| 5 | Postgres, explicit memory, privacy | ✅ Offline scaffold (SQLite/dev); prod OIDC/RLS pending |
| 6 | Eval suite, hardening, cost report | ✅ Offline mock eval + reports; paid/load incomplete |
| 7 | Deploy + final report | 📋 Infra planned; UpCloud not provisioned (`docs/35`–`39`) |

Cut order if late (from roadmap): camera → WebRTC → semantic vectors → extra gestures. **Never cut:** text fallback, consent, mock mode, schema validation, core tests.

---

## 12. What is LEFT to make her “perfect” (prioritized backlog)

Use this as the work queue. Do not skip gates.

### Tier A — Conversation intelligence (highest ROI for “she talks perfectly”)

1. **Approve capped real Gemini + Azure live test** — measure Nepali STT/TTS/LLM quality & latency (`scripts/run_tier_a_provider_gate.py`, `docs/07-nepali-voice-evaluation.md`).
2. ~~**Wire multi-layer prompt assembly**~~ ✅ Done offline — `apps/api/hinaa_api/prompts/`.
3. ~~**Enrich live mode** server-owned allowlisted performance planning~~ ✅ Done offline (heuristic planner; not Phase 4 clock).
4. ~~**Response-depth guidance** for REST vs realtime~~ ✅ Done offline.
5. ~~**Prompt versioning + fingerprint + regression canaries**~~ ✅ Done offline.

### Tier B — Memory & personalization (makes her feel “hers”)

6. PostgreSQL migrations + session persistence.
7. Explicit memory: remember / forget / list + consent.
8. Conversation summarizer for long chats.
9. Privacy dashboard + delete-all.
10. (Later) pgvector semantic retrieval — cuttable if late.

### Tier C — Presence (makes her feel alive)

11. Licence-approve one VRM; install Three.js / R3F / `@pixiv/three-vrm`.
12. Phase 4 performance clock: emotion/gesture allowlists synced to speech.
13. Visemes / better lips; 5–10 polished motions.
14. (Later) custom licensed voice identity.

### Tier D — Advanced assistant capabilities (after core soul is solid)

15. Controlled tool planner (search, calendar, etc.) behind permissions.
16. Optional multi-provider brain routing (still Gemini-first).
17. Vision / camera (post-MVP in current scope).
18. Auth, multi-device sync, deploy hardening, eval suite Phase 6–7.

### Tier E — Product polish

19. Trusted HTTPS for Android mic.
20. Commit Phase 3 after owner approval.
21. Accessibility, cost reporting, final demo contingency (mock video).

---

## 13. How to run (local)

```powershell
# Validate blueprint
python scripts/validate_blueprint.py

# Phase 3 mock/realtime UI
.\scripts\start-phase3.ps1
# → http://127.0.0.1:5173/
```

Mock needs no keys. Real providers need `apps/api/.env.local` and **explicit owner approval** for paid streaming tests.

---

## 14. Hard rules for any AI editing this repo

1. Read this file + relevant phase review before coding.
2. Do not load quarantined VRM/ZIP assets or claim licence clearance.
3. Do not put secrets in `VITE_*`, docs, or commits.
4. Do not enable unrestricted tools or consciousness-claiming prompts.
5. Do not start Phase 4+ or commit/push unless owner explicitly asks.
6. Prefer mock-testable changes; keep text-only and mock paths green.
7. Preserve `AssistantTurnPlan` schema validation — never let free-form model output drive bones/tools.
8. Companion personality changes must not weaken safety layers.
9. Prefer small vertical slices with tests over giant rewrites.
10. When unsure: check `docs/20-open-questions.md` and ask the owner.

---

## 15. Suggested prompt when handing this to another AI

```text
You are continuing the HINAA / Hina project in folder HINAMYGIRL.
Read docs/HINA-MASTER-BLUEPRINT-FOR-AI.md fully, then the linked docs for your task.
Current state: Phase 0–3 offline complete; real Azure/Gemini streaming gated;
personality layers and Postgres memory are NOT wired; VRM quarantined;
procedural avatar only. Goal: [DESCRIBE TASK]. Respect safety, asset quarantine,
no commit/push unless I ask. Prefer mock-testable implementation.
```

---

## 16. Quick verdict for humans

**What you have:** A serious, well-architected companion *pipeline* (capture → STT → LLM → TurnPlan → TTS → avatar cues) with excellent docs and offline demos.

**What you still need for “perfect conversing Hina”:** real provider quality loop → full personality brain → durable memory → then VRM presence → then advanced tools.

She is **blueprint-strong and pipeline-real**, not yet **soul-complete**.
