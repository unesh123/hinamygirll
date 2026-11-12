# Hina provider verification — 2026-11-12

Scope: repair provider selection/discovery and verify configured default models. This is not a full architecture, voice, avatar, autonomy, or production readiness sign-off. Existing concurrent work through commit `5a2b2fb` was preserved. No deployment, DNS, public tunnel, authentication-policy, or credential changes were made.

## Actual upstream checks

Synthetic prompt: “Reply with exactly the word Pong.” Each lane used its configured adapter/model, without fallback or retries. Success requires nonempty streamed text, not HTTP 200 or a model catalog. These are individual first-text samples, not a performance benchmark or full application response latency. Gateway model names are reported labels, not independently authenticated model identities.

| Configured lane | Observed result |
| --- | --- |
| XKiro / mistralai/codestral-2508 | Responded; 723 and 2590 ms to first text |
| Gemini / gemini-3.5-flash | Responded; 2650 and 1288 ms to first text |
| Experiential / claude-opus-5.5 | Responded; 3545 and 4872 ms to first text |
| GMI / deepseek-ai/deepseek-v4.1-flash-1017 | HTTP 402; repeated final check 2072 ms |
| Respan / gpt-4o-mini | HTTP 401; repeated final check 1039 ms |
| Custom / Kimi-K2.6 and Codecraft / claude-fable-5 | HTTP 402 |
| Claude gateway / claude-sonnet-4-6 | HTTP 403 |
| PGSGrove, TokenTable, Oxion | HTTP 401 |
| CX gateway | Correct normalized wire model returned 402, then 429 |
| APMIX | Inference HTTP 404 |
| SeekAI | HTTP 526 |
| Cavoti | HTTP 521 |
| Agent Router | HTTP 200, but timed out before text |
| Local Ollama | Connection failed |
| OpenAI, Groq, Qwen | Adapter reports missing configuration; no inference attempted |
| Articul8 Bivia | Local decision route returned 502 / BIVIA_AUTH_REJECTED; upstream credentials rejected |

An intermediate Gemini probe with a 64-token output budget returned no visible text. Increasing the diagnostic budget to 512 produced text in 1288 ms. No-text probes are inconclusive and are no longer persisted as health failures. An initial CX probe omitted adapter wire-name normalization; that 404 was a diagnostic defect and is superseded by the corrected 402/429 checks.

Raw sanitized evidence is local under `.runtime/`: `configured-chat-check.json`, `verified-chat-lanes.json`, `gemini-budget-check.json`, `cx-normalized-check.json`, `gmi-respan-final-check.json`, `provider-model-catalogs.json`, and `local-provider-verification.json`. The last local snapshot precedes the final GMI/Respan ledger writes. Health observations expire and are scoped to configuration fingerprints; they are not permanent availability guarantees.

HTTP 401/403 requires provider-side authentication/access investigation; 402 requires billing/account investigation; 404 requires endpoint/model validation. 429 and 521/526 require rate-limit or upstream availability recovery. No secrets were printed. Configured keys do not imply usable accounts.

## Repairs in this milestone

- `apps/api/hinaa_api/models.py`: accept `respan` in the typed provider contract; previously selecting it silently normalized to `real` (Gemini).
- `apps/api/hinaa_api/config.py`: expose GMI configuration/model properties consistently.
- `apps/api/hinaa_api/brain_ledger.py`: fingerprint GMI evidence using its own settings.
- `apps/api/hinaa_api/services.py`: include configured GMI/Respan in backend fallback candidates.
- `apps/api/hinaa_api/main.py`: expose GMI discovery; consolidate duplicate GMI status entries; require actual inference evidence before declaring a brain healthy, even if its catalog responds.
- `apps/web/src/features/providers/utils/resolveProviderSelection.ts`: include GMI/Respan in automatic recovery while preserving measured-health priority.
- `scripts/check_configured_chat.py`: bounded, secret-safe, explicit default-model probes; optional `--record` writes real observations into the existing ledger. No environment edits or hidden fallback.
- `apps/api/tests/test_provider_completeness.py`: mode preservation, discovery, unique provider IDs, fallback and catalog-versus-inference regressions.
- `apps/api/tests/test_configured_chat_check.py`: mocked stream/HTTP failure and text-evidence tests for the audit script.
- `apps/web/src/features/providers/utils/resolveProviderSelection.test.ts`: recovery coverage for both lanes.
- This report.

The Bivia decision adapter and removal of fabricated chat aliases are already in the preserved baseline. Bivia is a bounded decision API, not a general chat model: [official Bivia API](https://articul8.ai/bivia). Respan's public catalog cannot prove a credential works for inference: [chat endpoint](https://www.respan.ai/docs/apis/gateway/create-chat-completion), [model catalog](https://www.respan.ai/docs/apis/models/list-models).

## Validation

From repository root:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_provider_completeness.py apps/api/tests/test_bivia.py apps/api/tests/test_provider_security.py apps/api/tests/test_configured_chat_check.py -o addopts= -q
```

Result: **60 passed**, 6.81 seconds; one Google SDK deprecation warning. These tests mock upstream providers; they are not evidence that paid services work.

From `apps/web`:

```powershell
node node_modules/typescript/bin/tsc -b
node node_modules/vitest/vitest.mjs run src/features/providers/utils/resolveProviderSelection.test.ts src/design-system/chat/ModelSelectorV7.test.tsx --maxWorkers=2
node node_modules/vite/bin/vite.js build
```

TypeScript passed; **28 frontend tests passed**; production build passed. Large bundle warning remains. `git diff --check` passed (Windows line-ending notices only).

Live network probes used `scripts/check_configured_chat.py`; unlike the tests, those contacted configured services. A bounded rerun can use:

```powershell
apps/api/.venv/Scripts/python.exe scripts/check_configured_chat.py --modes real xkiro experiential --record
```

This makes actual billable requests. By default the script checks all listed lanes; each lane uses at most a 15-second deadline and total concurrency is three.

## Local runner and remaining verification

Started the existing local runner and refreshed its owned API child after the last fix. Verified API `/health/live` HTTP 200, frontend `http://127.0.0.1:5173/` HTTP 200, frontend proxy `/api/v1/providers` HTTP 200 with unique IDs, and API `/v1/capabilities` HTTP 200. The proxy reported Gemini, XKiro and Experiential healthy from recorded successful requests. The Bivia route was exercised with synthetic decision input and surfaced the authentication failure correctly.

No public deployment or public ingress verification occurred. Runner state reports local operation, no published origin, tunnel unhealthy. HTTP checks are not browser layout checks. End-to-end microphone/voice latency, avatar FPS, mobile layout, full streamed chat orchestration, all alternate model IDs, and unsupported/new service credentials remain unverified in this milestone. New environment variable names alone do not establish an integration; no speculative provider endpoints were added.

## Rollback

Do not reset files or roll back the baseline commits. Review `git diff` and reverse only the hunks listed above (including the GMI status consolidation), preserving any subsequent edits. Remove the new audit script, its new test, and this report only if they have no later work. Rebuild the frontend and restart the existing owned local runner afterward. Optional audit ledger entries naturally expire; do not delete the whole ledger or unrelated runtime files.
