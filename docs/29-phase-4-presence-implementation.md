# 29 — Phase 4 presence implementation

## Implemented (offline)

- Typed performance contracts: `apps/web/src/features/avatar/performanceTypes.ts`
- Monotonic client scheduler: `PerformanceScheduler`
- Semantic → procedural allowlist mapping (no bone/file names from model)
- Integration via `usePerformanceClock` into `ProceduralAvatar`
- Lip sync level: **amplitude only** (`lipSyncLevel: "amplitude"`)
- Reduced-motion intensity/gesture caps
- Interrupt clears generation and stale jaw/plan drive
- Procedural avatar remains the only runtime engine
- Text-only avatar fallback unchanged

## Motion library (semantic)

neutral_idle, friendly_greeting, small_nod, thoughtful_pause, listening, happy_ack, calm_reassure, mild_celebrate, apology_correction, return_neutral

## Licence / VRM status

**Not integrated.** All local VRMs remain quarantined per `docs/ASSET_LICENSES.md` (unknown/unverified fields). No Three.js/`@pixiv/three-vrm` installed.

## Tests

- `apps/web/src/features/avatar/performanceScheduler.test.ts`

## Limitations

- No Azure viseme timeline
- No polished VRMA motion clips
- No Phase 4 server performance clock (client scheduler consumes AssistantTurnPlan)
- VRM path remains interface-ready (`AvatarEngine.kind` includes `"vrm"`) but unused
