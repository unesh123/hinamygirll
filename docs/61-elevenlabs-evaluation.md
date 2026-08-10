# HINAA Document 61: ElevenLabs Voice & Multilingual Evaluation Framework

## Overview
This document defines the evaluation matrix and voice selection methodology for ElevenLabs TTS in HINAA prior to production deployment.

## Voice Entry Metadata Model
Each candidate voice MUST track:
- `display_name`: Human-readable identifier.
- `voice_id`: Upstream ElevenLabs GUID.
- `model_id`: ElevenLabs model string (e.g. `eleven_multilingual_v2`).
- `verified`: Boolean indicating owner-gated smoke test pass.
- `language_review`: Qualitative score per language domain.
- `streaming_verified`: Verified under chunked streaming.
- `commercial_use_status`: Commercial license compliance.

## Language Test Suite Matrix
Before marking a voice as verified for production, it must pass 12 phrase categories:
1. English (Natural conversational)
2. Nepali Devanagari (Clean pronunciation)
3. Romanized Nepali Intent (Handling Nepali phrase written in Latin script)
4. Hindi (Standard Devanagari)
5. Nepali-English Code Switching
6. Hindi-English Code Switching
7. Proper Names (Nepali & International)
8. Numbers & Ordinals
9. Currency (NPR / INR / USD)
10. Technical Identifiers (URLs, file paths, model names)
11. Long Complex Sentences (>200 chars)
12. Short Acknowledgements ("Hajur", "Okay", "Suney")

## Responsible Use & Policy Guidelines
- No voice cloning of real individuals, celebrities, or copyrighted characters.
- No synthetic voice impersonation without consent.
