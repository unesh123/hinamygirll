# 65: Voice Performance Planner & Semantic Modes

## 1. Overview
Server-owned `VoicePerformancePlanner` maps bounded LLM semantic modes into clamped provider settings.

The planner is persona-tuned: Hinaa's affectionate profile delivers every semantic mode with **more emotional warmth** — lower stability (more expressive range), higher style intensity, and a slightly slower, tenderer pace. Hiro keeps a calmer, more grounded delivery.

## 2. Semantic Mode Allowlist
- `neutral`
- `warm`
- `bright`
- `calm`
- `thoughtful`
- `professional`
- `encouraging`
- `playful`
- `celebratory`
- `apologetic`

## 3. Clamped Controls
- `deliveryMode`
- `stability` (0.0 – 1.0) — lower = more emotional/expressive
- `similarity` (0.0 – 1.0)
- `style_intensity` (0.0 – 1.0) — higher = more warmth/expressiveness
- `pace` (0.5 – 2.0) — below 1.0 = more tender/caring

## 4. Warmth Tuning (Hinaa persona)
Effective voice settings = semantic-mode baseline + per-companion bias, then clamped.

| Semantic mode | baseline stability | baseline style | baseline pace |
|---|---|---|---|
| `warm` (default conversational) | 0.42 | 0.28 | 0.93 |
| `bright` | 0.38 | 0.28 | 1.03 |
| `calm` | 0.60 | 0.12 | 0.90 |
| `thoughtful` | 0.58 | 0.10 | 0.90 |
| `professional` | 0.68 | 0.06 | 1.00 |
| `playful` | 0.33 | 0.38 | 1.06 |
| `celebratory` | 0.36 | 0.34 | 1.04 |
| `apologetic` | 0.58 | 0.16 | 0.92 |
| `encouraging` | 0.42 | 0.30 | 0.98 |

Per-companion bias: Hinaa adds `-0.05` stability, `+0.10` style, `-0.02` pace; Hiro adds `+0.06` stability, `-0.04` style, `-0.01` pace.

These settings are sent as ElevenLabs `voice_settings` (stability, similarity_boost, style, speed, use_speaker_boost=true) on every HTTP TTS call.
