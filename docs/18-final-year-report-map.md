# Final-year academic report map

## Purpose

Frame HINAA as a research project rather than only a product build.

## Decision

**Problem statement:** Mainstream assistants underserve informal Nepali, Romanized Nepali and multilingual code-switching, while 3D companions add latency/performance complexity and potential social/privacy harms.

**Contribution:** design and evaluation of a low-latency, emotion-aware, multilingual 3D conversational assistant for Nepali and code-switched speech.

**Research questions:** (RQ1) How accurately do available STT systems recognize Devanagari, Romanized and code-switched Nepali? (RQ2) How does synchronized facial expression/gesture affect perceived naturalness? (RQ3) Which voice pipeline best balances latency, accuracy, privacy and cost? (RQ4) Can adaptive 3D rendering maintain acceptable performance on ordinary Android hardware?

**Objectives:** implement one ethical MVP loop; create/review an original 1,000-item set; benchmark providers; compare avatar timing conditions; measure mobile performance; document privacy/safety.

**Scope/limitations:** small nonrepresentative speaker/rater sample, two characters, selected devices/providers, lab-like network, short-term perceptions, no clinical/emotional inference, no commercial-scale conclusions.

### Chapter mapping

| Chapter | Evidence |
|---|---|
| 1 Introduction | vision, problem, RQs, scope |
| 2 Literature review | Nepali ASR/TTS, code-switching, embodied agents, lip-sync, affective UX, HCI ethics/privacy, realtime systems |
| 3 Requirements/method | stories, architecture, dataset/study protocol, ethics |
| 4 Design | events, provider routing, avatar, memory, UX, threat model, ADRs |
| 5 Implementation | later Phase 1–5 commits and tests; blueprint is not claimed as implementation |
| 6 Evaluation | WER/CER, latency/cost, MOS, avatar study, FPS/accessibility/security |
| 7 Results/discussion | confidence intervals, trade-offs, failure cases, threats to validity |
| 8 Conclusion/future work | answered RQs, limitations, post-MVP boundary |

### Ethics

Supervisor/institution approval before human recording/study; informed consent, adult participants unless separately approved, withdrawal, pseudonyms, minimum collection, encrypted restricted storage, no deceptive consciousness claims, no mental-state inference, and disclosure of provider processing.

### Final demo script (8–10 min)

1. State contribution/scope and show privacy-first onboarding.
2. Switch companions and quality/text modes.
3. Romanized Nepali/code-switch tap-to-talk with partial transcript.
4. Stream answer, voice, face/gesture/lips; interrupt mid-speech.
5. Explicitly remember, inspect and forget a harmless preference.
6. Simulate provider failure and show fallback.
7. Show benchmark/results dashboard and device FPS.
8. Disable network/WebGL and complete mock/text turn.
9. End with limitations and no-tool/no-surveillance boundary.

## Alternatives considered

A feature checklist alone offers weak academic novelty. Controlled measurements answer concrete RQs.

## Reasoning

Each research question has an artifact, metric and analysis method.

## Risks

Underpowered subjective study and confirmation bias. Predefine hypotheses/metrics, randomize order, report effect sizes/intervals and negative findings.

## Acceptance criteria

Report never generalizes beyond sample/devices; all participant data has consent and a deletion path; results trace to reproducible run IDs.

