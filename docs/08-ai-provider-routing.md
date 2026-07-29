# AI provider routing

## Purpose

Select healthy, capable providers without coupling product behavior to one vendor or model.

## Decision

Adapters implement the ports in [provider SDK](../packages/provider-sdk/README.md). At session start, capability discovery builds eligible candidates. Hard filters apply enabled status, user selection, capability, language, privacy mode, BYOK/platform credential availability, region and policy. Weighted scoring then considers health, p95 latency, estimated cost, remaining quota and circuit state. Explicit user selection wins only if all hard constraints pass.

MVP candidate route: Azure Speech cascade + configured Gemini conversation model. `gemini-3.6-flash` and `gemini-3.5-flash-lite` were officially listed on 2026-07-30, but aliases are configuration and require a startup capability check. Google AI Pro is not treated as Gemini API billing. Cursor/Verdent are development tools only. `api.hcnsec.cn` is denylisted; no adapter, key field, DNS request, or fallback targets it.

### Resilience policy

| Operation | Connect/first-byte | Total | Retries |
|---|---:|---:|---:|
| STT stream start | 3 s | session-bound | 1 before audio accepted |
| LLM first token | 8 s | 30 s | 1 if idempotent/no output |
| TTS first audio | 8 s | 30 s | 1 if no audio emitted |
| Embedding | 5 s | 15 s | 2 |

Retry uses exponential backoff with full jitter: `random(0, min(8s, 250ms*2^attempt))`. Never retry after visible partial audio/text unless the old generation is cancelled and the UI labels fallback. Circuit opens after 5 eligible failures in 60 s, remains open 30 s, admits one half-open probe, and closes after 2 successes. Rate limits honor `Retry-After`. Health data is regional and capability-specific.

Fallback order is session-selected provider → configured language-capable alternative → text-only response → deterministic mock for demo. The user sees a nontechnical message and can inspect provider status; logs use category, adapter version, latency, status and trace ID without prompts/keys.

### BYOK (post-MVP design)

Credentials travel over TLS to a dedicated endpoint, are envelope-encrypted with a per-record data key and KMS/Key Vault master key, and are never returned. Store ciphertext, nonce, wrapped key, provider, owner, masked suffix, created/rotated/revoked timestamps. Separate platform/user credentials, apply quotas, audit test/rotate/revoke/delete, use ephemeral realtime tokens, and mark invalid/rate-limited keys without silently charging platform fallback unless the user permits it.

## Alternatives considered

Hard-coded provider chains cannot honor privacy/cost/health. An AI-based router is nondeterministic and unsafe for credentials. Deterministic filter/score rules are auditable.

## Reasoning

Capability negotiation plus circuit breaking enables benchmark-driven defaults and graceful demo behavior.

## Risks

Fallback can change privacy/cost semantics and duplicate billing. Require route consent, idempotency keys, usage ledger reconciliation and clear provider transitions.

## Acceptance criteria

- Provider contract suite runs against mock and every enabled adapter.
- A provider with missing Nepali capability is never selected for required Nepali output.
- Denylisted hosts cannot be configured.
- Timeout/rate-limit tests yield one clear user message and no duplicate completed turn.

## Verified sources (2026-07-30)

[Gemini models/pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini availability including Nepal](https://ai.google.dev/gemini-api/docs/available-regions), [Azure Speech languages](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support).

