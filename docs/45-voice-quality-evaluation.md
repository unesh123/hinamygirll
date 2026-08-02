# 45 — Voice quality evaluation

## Current licensed path

- Provider: Azure Speech neural voices (configured names in backend env)
- Default female: `ne-NP-HemkalaNeural` (Hinaa)
- Default male: `ne-NP-SagarNeural` (Hiro)
- Not a custom-trained HINAA voice
- Not a celebrity or personal clone

## VoicePerformancePlan

Bounded server fields: mode, pace, pitch, volume, warmth, energy.

Modes: `neutral`, `warm`, `bright`, `calm`, `professional`, `celebratory`,
`thoughtful`, `apologetic`. No flirt/sexual mode.

Speech-only pronunciation map adjusts TTS text for names/tech terms; display
text stays unchanged.

SSML tags are allowlisted (`speak`, `prosody`, `break`); models never emit raw SSML.

## Evaluation status

Real subjective quality remains **unverified** until the owner-gated two-turn
provider script runs and audio is manually reviewed.
