# Cost and subscription plan

## Purpose

Control student spending without freezing changeable vendor prices into architecture.

## Decision

### Operating tiers

| Tier | Components | Guardrails |
|---|---|---|
| A free development | mock providers, local assets/database, optional browser features | no key needed, synthetic data, CI minute awareness |
| B student-credit MVP | official Gemini/Azure test quotas, Azure Speech/backend experiment | $5 warning, $10 hard monthly project target where controls permit; daily caps; demo-only deployment |
| C production pilot | paid official APIs, managed DB/hosting/storage/observability/backups | per-user/provider quotas, prepaid/budget alerts, usage ledger, kill switch; subscriptions post-MVP |

Google’s pricing page on 2026-07-30 lists Gemini free and paid tiers and says free-tier content may be used to improve products while paid-tier content is not. Therefore unpaid testing uses synthetic/non-sensitive data. Google AI Pro is not booked as API credit. Azure for Students currently advertises $100 for 12 months; eligibility/quota is verified in the owner’s portal before planning. Do not buy ElevenLabs, GPU hosting, custom avatars, additional LLM subscriptions, or grey-market keys before benchmark evidence.

### Cost model

Keep rates in a dated configuration sheet copied from official calculators, never source code. For month `m`:

`C = H_api + H_db + H_storage + H_egress + M_stt*r_stt + Ch_tts*r_tts + Tok_in*r_in + Tok_out*r_out + Min_rt*r_rt + C_obs + C_backup + tax`.

Scenarios are workload inputs, not invented currency totals:

| Input/month | Low | Expected | High |
|---|---:|---:|---:|
| active demo users | 1 | 10 | 50 |
| sessions/user | 10 | 20 | 40 |
| minutes/session | 3 | 7 | 10 |
| input/output tokens/min | 250/120 | 400/180 | 700/300 |
| TTS chars/min | 300 | 500 | 750 |
| stored history/user | 5 MB | 25 MB | 100 MB |

The cost worksheet multiplies these by current rates and shows provider, date, currency, free allowance, tax/egress exclusions, low/expected/high totals and remaining Azure credit. Cost per 10-minute session uses the same formula with ten minutes.

Subscriptions are future-only: enforce entitlements server-side, reconcile provider usage IDs, reserve/refund estimated units, never trust client counters, and fail gracefully at quota. MVP has no payments.

## Alternatives considered

Publishing numeric forecasts with volatile rates becomes misleading. Formulas plus dated official-rate inputs are auditable.

## Reasoning

Student credits are a constraint, not a reliable architecture dependency.

## Risks

Free-tier policy changes, token/audio units differ, retries duplicate cost, and currencies/taxes vary. Reverify weekly during evaluation and before demo.

## Acceptance criteria

- Budget alerts and a server kill switch are tested before any paid route.
- Usage ledger reconciles >=99% of provider request IDs in benchmark runs.
- Rate sheet links and verification date are visible.
- No unofficial reseller is funded or enabled.

## Official pricing sources checked 2026-07-30

[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/), [Azure for Students](https://azure.microsoft.com/en-us/free/students).

