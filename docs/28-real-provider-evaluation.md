# 28 — Real provider evaluation

## Status: **Gemini smoke PASS · Azure voice NOT tested · latency too high for natural voice**

Checkpoint commit: `24f7071` on `phase/3-live-streaming`.
Working-tree local-live upgrades may exist beyond the checkpoint.

## Owner-run paid Gemini gate (observed; do not repeat without new authorization)

Gate variables were set by the owner in the executing shell. Script completed after
exactly two turns. Cap respected. No commit performed.

### Configured model

`gemini-3.6-flash`

### Turn 1 (romanized-ne-en)

| Field | Observed |
|---|---|
| provider | `gemini:gemini-3.6-flash` |
| model | `gemini-3.6-flash` |
| latencyMs | 7940 |
| firstDeltaMs | 7946 |
| totalMs | 7962 |
| schemaValid | True |
| spokenChars | 77 |
| emotion | thinking |
| gesture | explain |
| toolRequests | [] |
| language | mixed |

### Turn 2 (hi-en-technical)

| Field | Observed |
|---|---|
| provider | `gemini:gemini-3.6-flash` |
| model | `gemini-3.6-flash` |
| latencyMs | 7246 |
| firstDeltaMs | 7245 |
| totalMs | 7248 |
| schemaValid | True |
| spokenChars | 114 |
| emotion | thinking |
| gesture | explain |
| toolRequests | [] |
| language | mixed |

### What this gate exercised

- Gemini authentication: PASS
- Configured model availability: PASS
- `ConversationService.create_live_plan` → `GeminiLLMProvider.create_live_plan`
- `generate_content_stream` with `response_mime_type=text/plain`
- Server-side `AssistantTurnPlan` construction via `build_plan_from_text` after text completes
- Schema validity of constructed plans: PASS × 2

### What this gate did **not** exercise

- Azure STT: **NOT TESTED**
- Azure TTS: **NOT TESTED**
- Hemkala / Sagar audio listening: **NOT TESTED**
- WebSocket `/v1/realtime`: **NOT TESTED**
- REST structured JSON plan generation (`create_plan` / `application/json`): **NOT TESTED**
- Microphone / mobile / barge-in: **NOT TESTED**

### Latency interpretation (code analysis; no extra paid calls)

- Gate wall clock starts immediately before `create_live_plan`.
- `firstDeltaMs` is wall-clock time until the first `emit_delta` callback with a
  non-empty sanitized stream chunk. It is **not** plan-validation time.
- Observed `firstDeltaMs ≈ totalMs` for both turns ⇒ the first non-empty text
  chunk arrived essentially at response completion for these short replies.
- `latencyMs` is measured inside the Gemini adapter around client create + stream
  + plan build (excludes little outside work; nearly matches wall `totalMs`).
- Emotion/gesture `thinking`/`explain` come from **server heuristic** performance
  planning after text completes, not from a model JSON plan.
- Schema-repair path was **not** used (`create_live_plan` does not call `_repair_json`).
- A **new** `genai.Client` is constructed per turn today; HTTP reuse across turns
  is not implemented.
- Static prompt layers are reassembled each turn (~6k system chars offline for the
  turn-1 style prompt); caching is not yet implemented.
- `thinking_config` is unset in code; model-default thinking behavior for
  `gemini-3.6-flash` remains a candidate contributor and needs stage evidence on a
  future authorized run (`first_provider_event` vs `first_text_delta`).

Do **not** claim full multilingual quality from two short responses.

## Instrumentation added (offline; for next authorized run)

Sanitized stages (ms from start, omit if absent):

`prompt_built`, `provider_client_ready`, `request_sent`, `first_provider_event`,
`first_text_delta`, `text_complete`, `plan_parsed`, `plan_validated`

Ordinary tests remain provider-free. Mock path unit-tests the timing object.

## Prepared Azure TTS smoke (owner-run; agent must not execute)

Separate gate from the Gemini text gate. One phrase only. No STT.

```powershell
$env:HINAA_ALLOW_PAID_VOICE_TEST="1"
$env:HINAA_PAID_VOICE_TEST_CONFIRM="I_UNDERSTAND_THIS_MAY_COST_MONEY"
apps\api\.venv\Scripts\python.exe scripts\run_azure_tts_smoke.py
```

Optional listen file (gitignored): add `--keep-audio`.

## Non-billable pre-checks

| Check | Result |
|---|---|
| `apps/api/.env.local` ignored by Git | Yes |
| Secret names present (values not displayed) | Yes |
| Gate capped at max 2 turns | Yes |
| Ordinary pytest cannot call paid gates | Yes |

## Failed

- None for Gemini authentication/schema on the owner run
- Voice naturalness goal: first text too slow (~7.2–8.0s) for conversational voice

## Blocked / next

1. Use new timing stages on a future authorized Gemini run (not this task).
2. Owner-run Hemkala TTS smoke when ready (`run_azure_tts_smoke.py`).
3. Do not rewrite the voice pipeline without stage evidence from another authorized run.
