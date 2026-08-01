# 28 — Real provider evaluation

## Status: **Not run**

Owner authorization variables were absent:

- `HINAA_ALLOW_PAID_PROVIDER_TEST` unset
- `HINAA_PAID_PROVIDER_TEST_CONFIRM` unset

Refusal behavior verified: `scripts/run_tier_a_provider_gate.py` exits 2.

## Offline preparation completed

- Evaluation case corpus: `apps/api/tests/fixtures/real_provider_eval_cases.json`
- Covers language mixes, companion IDs, and safety prompts
- No credentials invented or displayed
- No billable calls performed

## Exact owner command (when authorized)

```powershell
$env:HINAA_ALLOW_PAID_PROVIDER_TEST="1"
$env:HINAA_PAID_PROVIDER_TEST_CONFIRM="I_UNDERSTAND_THIS_MAY_COST_MONEY"
apps\api\.venv\Scripts\python.exe scripts\run_tier_a_provider_gate.py --max-turns 2
```

Requires ignored `apps/api/.env.local` with Azure + Gemini keys. Never place keys in `VITE_*`.

## Observation table

| Scenario family | Status |
|---|---|
| Language mixes | Not run |
| Conversation styles | Not run |
| Realtime timings | Not run |
| Safety red-team live | Not run (offline injection corpus exists in Tier A unit tests) |
| Cost / usage | Unavailable |

Do not treat this gate as complete.
