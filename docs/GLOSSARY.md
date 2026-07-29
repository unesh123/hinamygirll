# Glossary

## Purpose

Explain project terminology for a student reader.

## Decision

| Term | Plain explanation |
|---|---|
| Adapter | Small module translating HINAA’s interface to one provider SDK/API. |
| ADR | Dated record of a major decision, alternatives and consequences. |
| Barge-in | User interrupts while the assistant is speaking. |
| BYOK | Bring Your Own Key; future encrypted user provider credentials. |
| Cascade | Separate STT → language model → TTS voice path. |
| CER/WER | Character/word error rate for transcription; lower is better. |
| Circuit breaker | Temporarily stops calls to a repeatedly failing provider. |
| Code-switching | Mixing languages in one conversation or sentence. |
| Envelope encryption | Encrypt data with a data key, then protect that key with a master KMS key. |
| HNSW/IVFFlat | Approximate vector-search index types; benchmark before choosing. |
| Idempotency | Repeating a request has no extra side effect. |
| LLM | Language model producing text/structured plans. |
| MOS | Human 1–5 mean opinion score for voice quality. |
| PWA | Website installable like an app with offline-capable resources. |
| RLS | PostgreSQL row-level security restricting which user rows can be read. |
| RMS | Audio energy measure used for fallback mouth movement. |
| RPO/RTO | Maximum data loss window / recovery time target. |
| SSE | One-way server-to-browser event stream. |
| STT/TTS | Speech-to-text / text-to-speech. |
| TurnPlan | Validated text, emotion and performance instructions for one reply. |
| Viseme | Visible mouth shape corresponding approximately to speech sound. |
| VRM/VRMA | 3D humanoid avatar format / reusable VRM animation format. |
| WebRTC | Low-latency browser media transport. |
| WebSocket | Persistent two-way application message connection. |

## Alternatives considered

Leaving acronyms unexplained would make the blueprint less useful academically.

## Reasoning

Plain definitions support report readers without removing technical precision.

## Risks

Terms evolve; update alongside contracts.

## Acceptance criteria

Every specialized acronym used repeatedly in the blueprint appears here or is defined in place.

