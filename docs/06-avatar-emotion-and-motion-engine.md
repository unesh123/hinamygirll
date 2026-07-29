# Avatar, emotion and motion engine

## Purpose

Make two VRM characters feel alive while keeping model output safe, repeatable, and mobile-friendly.

## Decision

The engine compiles a validated `AssistantTurnPlan` into five layers driven by one `AudioContext.currentTime` clock:

1. **Base life**: breathing, 2–6 s stochastic blinks, micro-gaze, posture and spring bones.
2. **Conversation state**: idle, listening, thinking, speaking, interrupted, celebrating, concerned, error recovery.
3. **Face**: neutral, soft/big smile, blush, pout, concerned, surprised, thinking plus VRM A/I/U/E/O.
4. **Gesture**: none, nod, shake, head tilt, wave, explain, celebrate, reassure, listening lean.
5. **Lip-sync**: timed visemes; estimated transcript vowels; smoothed audio energy last.

Priorities are safety/error/interrupted (100), state transition (80), semantic gesture (60), emotion (40), base life (10). Higher layers may suppress conflicting lower channels but not unrelated channels. Face masks reserve mouth weights for lip-sync while emotion uses eyes/brows/cheeks.

### Transitions and repetition

State blends: 250–400 ms; major posture: 400–600 ms; facial emotion: 150–300 ms; interruption to neutral/listening: <=200 ms. Major gestures have a 2–4 s spacing, 8 s per-gesture cooldown, and history of last five choices. Parameters may vary only within allowlists: speed 0.92–1.08, intensity ±0.1, start offset ±150 ms, safe gaze alternatives. Three intensity variants are preferred. No gesture triggers solely on audio peaks.

### Mood engine

Mood is server-side bounded state `{valence:-0.5..0.5, arousal:-0.4..0.6}`. Each eligible non-sensitive turn applies at most ±0.08 valence/±0.10 arousal. Exponential decay toward neutral has a 20-minute active-conversation half-life; after 2 hours inactive the next session begins within ±0.05; “reset mood” immediately returns neutral. Mood never changes safety, facts, consent, tool permissions, or user slider values. Distress signals select concerned tone without asserting a diagnosis.

### Lip-sync

Preference: provider viseme/phoneme timing → word boundaries plus deterministic grapheme/vowel estimator → RMS jaw energy. Energy fallback uses 15 ms analysis windows, silence gate approximately -45 dBFS (device-calibrated), 35 ms attack, 90 ms release, and clamp 0–0.65. Transcript estimation maps Devanagari/Latin phoneme approximations to A/I/U/E/O, cross-fades 50–90 ms, and calibrates output offset per device. Nepali Azure voices must be benchmarked because official voice availability does not itself guarantee viseme events.

### Quality tiers

| Tier | Budget |
|---|---|
| High | 45–60 FPS, shadows, full springs, enhanced light; optional postprocessing off by default |
| Medium | one shadow light, reduced spring iterations, no postprocessing |
| Low | 30 FPS target, no shadows, limited springs, lower pixel ratio, fewer layers |
| Emergency | static licensed portrait or text-only; all controls remain usable |

Initial asset targets: 30k–60k triangles, 2–4 primary draw calls/materials, mostly 1K textures (2K face maximum), compressed model <=20 MB. These are benchmark budgets, not VRM rules.

### Legal asset pipeline

Concept sheet → original/commissioned VRoid/Blender creation → VRM 1.0 → texture/material optimization → expression/spring validation → licensed motion retargeting to VRMA → mobile profiling → licence manifest/checksum → device test. Untrusted GLB/VRM is scanned, size-limited, decoded off the main path, never allowed external URI fetching, and served from isolated signed storage.

## Alternatives considered

Thousands of random clips increase size and repetition; direct LLM bone commands are unsafe; energy-only lips are cheap but inaccurate. Layered, allowlisted performance yields more variety with fewer assets.

## Reasoning

Separating state, face, gesture and mouth prevents expression conflicts and supports an ablation study.

## Risks

VRM 0.x/1.0 differences, animation clipping, mobile thermal throttling, and imperfect Nepali mouth estimation. Validate per asset and degrade automatically from rolling frame-time/thermal signals.

## Acceptance criteria

- No snap > one frame during normal transitions.
- Same major gesture is not repeated inside cooldown.
- Invalid filenames/bones/cues are rejected.
- Text-only mode survives WebGL/model/animation failure.

