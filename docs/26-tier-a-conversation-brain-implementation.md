# Tier A conversation brain — implementation report

## 1. Objective

Wire a production-quality layered prompt and conversation-planning system so Hinaa and Hiro feel more natural, multilingual, and coherent, without starting Phase 4+, durable memory, VRM, tools, or paid provider calls.

## 2. Baseline (before changes)

| Check | Result |
|---|---|
| `python scripts/validate_blueprint.py` | PASSED |
| `pytest apps/api/tests` | 20 passed |

Branch: `phase/3-live-streaming` @ `d8653ef` (Phase 3 work already uncommitted).

## 3. Architecture implemented

Executable package: `apps/api/hinaa_api/prompts/`

Deterministic assembly order:

1. immutable safety/privacy  
2. product identity / AI transparency  
3. companion identity (Hinaa ≠ Hiro)  
4. multilingual / code-switching  
5. bounded personality + mood  
6. response-depth guidance (REST vs realtime)  
7. tool policy (empty tools)  
8. schema / allowlist contract  
9. approved memory block (empty today)  
10. untrusted conversation history  
11. untrusted user message  

`ConversationService` builds a `PromptPackage` once per turn for both REST and realtime. Gemini consumes `system_instruction` + `user_contents`. Live mode still streams sanitized text first; the server attaches allowlisted emotion/performance via `plan_performance`. REST prefers structured JSON with one schema-repair attempt, then neutral fallback.

Prompt version: `tier-a-conversation-brain-1.0.0`  
Safety policy version: `safety-1.0.0`  
Companion profile version: `companions-1.0.0`  
Fingerprint: SHA-256 over normalized layers (no secrets).

## 4. Files changed / created

### Created
- `apps/api/hinaa_api/prompts/` (assembly, models, safety, companions, language, performance, depth, context, fallback, versioning, turn_prompt)
- `apps/api/tests/test_prompt_assembly.py`
- `apps/api/tests/test_conversation_brain.py`
- `scripts/run_tier_a_provider_gate.py`
- `docs/26-tier-a-conversation-brain-implementation.md`
- `docs/prompts/TIER-A-RUNTIME.md`

### Modified
- `apps/api/hinaa_api/config.py` — personality/history/debug settings
- `apps/api/hinaa_api/models.py` — optional `personality` on `TurnRequest`
- `apps/api/hinaa_api/services.py` — shared prompt assembly + fallback
- `apps/api/hinaa_api/providers/gemini.py` — consumes `PromptPackage`
- `apps/api/hinaa_api/providers/mock.py` — companion-differentiated mock brain
- `apps/api/hinaa_api/providers/base.py` — optional prompt argument
- `openapi/hinaa-api.yaml` — optional personality object
- `.env.example` — non-secret Tier A knobs + paid-gate notes
- `docs/HINA-MASTER-BLUEPRINT-FOR-AI.md` — status update
- `docs/prompts/README.md` — runtime pointer

## 5. Tests added

- Layer order / canaries / fingerprint stability
- Companion differentiation with identical safety
- Personality clamp bounds
- Response-depth inference
- History budgeting + untrusted delimiting
- Multilingual assembly fixtures
- Performance allowlists / serious defaults
- Fallback + invalid plan parsing
- Mock injection corpus
- Session isolation
- REST stream + optional personality compatibility

## 6. Commands executed and results

| Command | Result |
|---|---|
| `python scripts/validate_blueprint.py` | PASSED |
| `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests -q` | **51 passed** |
| `pnpm test` (apps/web) | **22 passed** (8 files) |
| `pnpm typecheck` | PASSED |
| `pnpm lint` | PASSED |
| `pnpm build` | PASSED (PWA precache 8 entries) |
| `pnpm exec playwright test --workers=2` | **14 passed** (full parallel workers=14 hit browser setup timeouts in this environment; workers=2 is green) |
| `scripts/run_tier_a_provider_gate.py` without flags | Exit 2 refuse (correct) |

## 7. Remaining owner-gated work

Real Gemini + Azure streaming quality measurement remains gated:

```powershell
$env:HINAA_ALLOW_PAID_PROVIDER_TEST="1"
$env:HINAA_PAID_PROVIDER_TEST_CONFIRM="I_UNDERSTAND_THIS_MAY_COST_MONEY"
apps\api\.venv\Scripts\python.exe scripts\run_tier_a_provider_gate.py --max-turns 2
```

Requires ignored `apps/api/.env.local` credentials. Not run during this implementation.

## 8. Known limitations (still incomplete)

- No PostgreSQL / durable memory / privacy dashboard
- No VRM / visemes / Phase 4 performance clock
- No tools / vision / custom voice
- Live emotion/performance is server-heuristic, not model-chosen structured live JSON
- Real-provider language quality not measured
- No commit or push performed

## 9. Recommended next safe step

1. Owner-approved capped paid provider gate above  
2. Then Phase 5 explicit memory, or licensed VRM intake — not both at once
