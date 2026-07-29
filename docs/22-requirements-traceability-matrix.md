# Requirements traceability matrix

## Purpose

Map every final-year MVP requirement to design, phase and acceptance evidence.

## Decision

| Req | Requirement | Design owner | Phase | Acceptance test |
|---|---|---|---|---|
| MVP-01 | installable mobile-first PWA | UX/deployment | 1 | E2E install, 320px/tablet/landscape |
| MVP-02 | responsive VRM playground | avatar engine | 1 | device FPS + WebGL-loss test |
| MVP-03 | female/male switch | companion/profile + assets | 1 | E2E switch without history loss |
| MVP-04 | text conversation | chat/orchestrator | 1–2 | mock and provider contract E2E |
| MVP-05 | tap/push-to-talk | audio client/realtime | 2–3 | permission and capture E2E |
| MVP-06 | partial transcription | STT/realtime protocol | 2–3 | ordered partial/final fixture |
| MVP-07 | streaming response | LLM/realtime protocol | 2–3 | delta/completed contract |
| MVP-08 | Nepali voice I/O | STT/TTS adapters | 2,6 | sealed WER/MOS/latency report |
| MVP-09 | explicit UI states | client state machine | 1–3 | visual/state transition suite |
| MVP-10 | base life animation | avatar base layer | 1 | visual/reduced-motion regression |
| MVP-11 | lip-sync | shared clock/visemes | 4 | timing study and fallback tests |
| MVP-12 | emotion face/gestures | TurnPlan/compiler | 4 | schema + human appropriateness study |
| MVP-13 | safe barge-in | local audio + cancellation | 3 | local stop p95 <=250 ms target; no late audio |
| MVP-14 | conversation history | DB/conversations | 5 | persistence/delete/RLS tests |
| MVP-15 | approved memory | consent/memory | 5 | no-write-before-consent + CRUD/delete |
| MVP-16 | provider selection/fallback | router | 2–3 | health/rate/timeout/circuit tests |
| MVP-17 | no-cost mock mode | mock adapters/service worker | 1 | offline full-turn E2E with no keys |
| MVP-18 | weak-phone degradation | quality governor | 1,6 | high→low→static automated/profile test |
| MVP-19 | opt-in camera experiment | privacy/vision boundary | 6 or cut | JIT permission/indicator/stop/delete test |
| MVP-20 | final live demonstration | demo script/deployment | 7 | rehearsed 8–10 minute script + offline fallback |

Cross-cutting language/personality/security/accessibility requirements are gates on all applicable rows: mixed-language dataset, bounded settings/mood, STRIDE controls, WCAG checks, safe uncertainty, no dependency manipulation, and server-only secrets.

### Phase 1 evidence — 2026-07-30

| Requirement | Phase 1 status | Evidence |
|---|---|---|
| MVP-01 | Pass for Phase 1 | Vite PWA manifest/service worker; production offline-reload tests on Pixel 5 and 320×568. |
| MVP-02 | Pass with approved placeholder | `AvatarEngine`/`ProceduralAvatarEngine`, responsive stage, WebGL-failure browser tests. Licensed VRM loading remains a later asset-gated increment. |
| MVP-03 | Partial | Hinaa/Hiro profile switching preserves transcript; actual female/male VRM assets remain quarantined. |
| MVP-04 | Pass for mock | Abortable deterministic provider streams local text with no network or key. |
| MVP-05 | UI mock only | “Try voice” simulates partial/final input and explicitly requests no permission; real capture remains Phase 2. |
| MVP-09 | Pass for Phase 1 | All six requested Phase 1 states plus deterministic `/error` component test. |
| MVP-10 | Pass for placeholder | CSS breathing, blink, gaze and subtle head movement; reduced-motion test and manual Pixel 5 inspection. |
| MVP-12 | Early partial | Zod mirror rejects extra/bone/file/tool values; mock emotion/gesture cues render. Human timing study remains Phase 4/6. |
| MVP-13 | Mock partial | Stop aborts active mock generation and enters interrupted state; measured audio stop remains Phase 3. |
| MVP-17 | Pass | Full local mock and offline PWA shell work without credentials. |
| MVP-18 | Pass for Phase 1 | 320×568/Pixel 5 tests, text-only, reduced motion and WebGL fallback. Automated quality/FPS governor remains Phase 6. |

Evidence commands and the complete file manifest are recorded in [Phase 1 review](23-phase-1-review.md).

Future-only trace: BYOK, device tools, image generation, payments/subscriptions, continuous vision, Capacitor, marketplace and desktop integrations are `POST-MVP` and cannot become grading dependencies.

## Alternatives considered

A checklist without tests cannot prove completion.

## Reasoning

Stable IDs link requirements, issues, test names and final report evidence.

## Risks

Rows can drift as scope changes. CI checks IDs; scope changes require supervisor approval and updated docs/tests.

## Acceptance criteria

All 20 rows have passing evidence or an explicitly approved scope change; no “implemented” claim relies only on manual observation.

