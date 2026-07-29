# Nepali voice and language evaluation

## Purpose

Select STT/TTS/realtime providers using evidence for actual HINAA language patterns.

## Decision

Benchmark Azure Speech `ne-NP` as cascade default candidate, one official realtime speech-to-speech API, and one modular alternative. Do not declare a winner before testing. Female candidate is `ne-NP-HemkalaNeural`; male candidate is `ne-NP-SagarNeural`, both confirmed in Microsoft’s catalog on 2026-07-30. Provider/model/voice IDs remain configuration.

### Original 1,000-utterance plan

| Category | Count |
|---|---:|
| Devanagari Nepali conversation | 180 |
| Romanized Nepali and spelling variants | 180 |
| Nepali-English code-switching | 180 |
| Nepali-Hindi-English mixtures | 100 |
| Assistant commands/questions | 100 |
| Interruptions/corrections/short answers | 80 |
| Names/dates/numbers/Nepali locations | 70 |
| Supportive/playful conversation | 60 |
| Hesitations/fillers/noisy speech | 50 |
| **Total** | **1,000** |

Use 600 development, 200 validation, 200 sealed test items, stratified by category/difficulty. Every sentence is original, reviewed independently by two native Nepali speakers, and stored as JSONL with `id,text,script,languageMix,intent,expectedNormalizedText,emotionGold,gestureGold,difficulty,split,license,reviewStatus`. The sealed set is not used for prompt/provider tuning.

Five consenting adults record 200 balanced items each. Record speaker pseudonym, dialect region (optional), device/noise condition, consent version and withdrawal status—not legal identity in the dataset. Aim for balanced gender presentation without making voice/gender claims. Audio is 16 kHz+ mono WAV master, encrypted at rest, access controlled, and deleted on withdrawal where technically possible. Public OpenSLR/Common Voice material may supplement but never replace code-switched items; verify licences per release.

### Metrics

- STT: raw and normalized WER/CER by category; Romanized token error rate; code-switch language preservation; name/number slot accuracy; first partial/final latency; correction rate.
- TTS: 1–5 MOS naturalness and pronunciation from >=10 native raters, intelligibility, code-switch pronunciation, first audio latency, duration, clipping.
- Conversation: semantic task success, language-match, unsupported-fact rate, schema validity.
- Realtime: p50/p95 interruption stop, first partial, first token and first audio.
- Cost: official metered units converted to `cost_10min = STT_minutes*r_stt + TTS_chars*r_tts + input_tokens*r_in + output_tokens*r_out + hosting_share`.

Report bootstrap 95% confidence intervals and paired comparisons on identical samples. Freeze provider versions/settings and record region, date, network, phone, microphone and retry policy.

### Human avatar study

Within-subject randomized comparison: A text/voice only, B audio-driven jaw, C synchronized emotion/gesture/lip plan. Measure perceived naturalness, responsiveness, appropriateness and distraction (1–5), plus preference and timing-error observation. Target 24–30 participants; obtain institutional supervisor/ethics approval and consent before recruitment.

## Alternatives considered

Public corpora alone underrepresent Romanized/code-switched casual HINAA speech. One-provider evaluation cannot support an academic routing decision.

## Reasoning

Balanced original items and sealed evaluation reduce overfitting while remaining achievable.

## Risks

Small speaker/rater samples, dialect bias, noisy subjective ratings, and provider drift. Publish limitations, inter-rater agreement, configurations, and raw aggregate results.

## Acceptance criteria

- Exactly 1,000 unique reviewed text items before final evaluation.
- No overlap between sealed items and prompt tuning.
- Provider recommendation includes accuracy, latency, naturalness, privacy and cost—not one metric.
- No sensitive production speech is sent through unpaid tiers whose terms permit product improvement.

## Verified sources (2026-07-30)

[Azure language/voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support), [Gemini API terms](https://ai.google.dev/gemini-api/terms), [Gemini pricing/data-use tier distinction](https://ai.google.dev/gemini-api/docs/pricing).

