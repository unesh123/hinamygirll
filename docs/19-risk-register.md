# Risk register

## Purpose

Track project, safety, technical and research risks with triggers and owners.

## Decision

Score probability (P) and impact (I) 1–5; exposure=P×I. Student owns delivery risks; supervisor owns ethics/scope approvals; asset owner owns provenance.

| ID | Risk | P/I | Trigger | Mitigation / contingency | Owner |
|---|---|---:|---|---|---|
| R1 | Nepali/code-switch STT below useful accuracy | 4/5 | sealed WER/slot errors exceed baseline threshold set W2 | benchmark early, transcript edit, text mode, narrow demo vocabulary claims | student |
| R2 | Voice lacks viseme timing | 4/3 | capability test returns none | word/vowel estimate + energy fallback; disclose limitation | student |
| R3 | Weak-phone FPS/thermal failure | 4/4 | p95 frame >33 ms/thermal throttle | tier governor, optimize assets, static/text fallback | student |
| R4 | Asset licence/provenance unclear | 4/5 | missing source/embedded terms | quarantine; replace with original/verified placeholder; no redistribution | asset owner |
| R5 | Provider quota/region/catalog changes | 3/4 | startup capability/billing failure | config IDs, mock, fallback, cache demo fixtures | student |
| R6 | Secret leakage | 2/5 | scan/canary alert | server-only secrets, rotate/revoke, incident plan | student |
| R7 | Cross-user history/memory leak | 2/5 | isolation test/authorization anomaly | RLS + service checks; block pilot on failure | student |
| R8 | Scope overrun | 5/4 | milestone slips >1 week | cut camera/direct realtime/vector/extra gestures in order | student/supervisor |
| R9 | Realtime cancellation race | 4/4 | audio after interruption | generation IDs, local stop, discard late frames, chaos tests | student |
| R10 | Prompt/personality manipulation | 3/5 | injection/boundary regression | immutable layers, schema, no tools, human review | student |
| R11 | Human-study recruitment/ethics delay | 3/4 | no approval by W8 | prepare protocol W1; reduce scope/report limitation, never bypass approval | supervisor |
| R12 | Cost overrun/billing abuse | 3/4 | 50/80% budget or usage anomaly | quotas, alerts, kill switch, mock default | student |
| R13 | Network fails live demo | 4/3 | unstable venue test | offline mock/text demo, cached assets, rehearsal, contingency recording | student |
| R14 | Camera creates privacy harm | 2/5 | ambiguous/on without request | cut from MVP first; JIT single-frame only | student/supervisor |
| R15 | OneDrive/large binary repo issues | 3/3 | sync conflicts/slow clone | private remote, LFS only licensed assets, checksums, separate backup | student |

Review weekly and at phase gates. Exposure >=15 blocks the next phase until mitigation evidence or supervisor-approved scope reduction.

## Alternatives considered

An unscored issue list does not create triggers or ownership.

## Reasoning

The register turns known uncertainty into early experiments and explicit cut lines.

## Risks

Scores are subjective. Record changes and supporting benchmark evidence.

## Acceptance criteria

No critical licence/security/ethics risk is accepted implicitly; weekly reviews are dated in project records.

