# 32 — Phase 6 evaluation report

## Offline suite

- Runner: `hinaa_api.evaluation.offline_suite.run_offline_mock_eval`
- Corpus: `apps/api/tests/fixtures/real_provider_eval_cases.json`
- Test: `apps/api/tests/test_offline_eval.py`
- Mode: **mock-offline only**
- Does **not** measure Gemini/Azure linguistic quality

## Categories covered offline

| Category | Coverage |
|---|---|
| Schema-valid plans | Yes (mock) |
| Companion IDs in corpus | Yes |
| Safety red-team strings | Partial (mock refusals + schema) |
| Realtime reliability | Covered by existing `test_realtime.py` + Playwright, not load-tested at scale |
| Memory isolation | Covered by `test_memory_privacy.py` |
| Accessibility | Existing Playwright/reduced-motion checks; full a11y audit incomplete |

## Not run

- Paid provider evaluation
- Load test against real Gemini/Azure
- Human Nepali reviewer scoring
- Full CSP/security penetration test
