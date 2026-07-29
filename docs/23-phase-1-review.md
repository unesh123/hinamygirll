# Phase 1 review gate

## Purpose

Record exactly what Phase 1 changed, how it was validated, and what remains blocked.

## Decision

Phase 1 is complete for review. It is frontend-only, deterministic, provider-free and asset-safe. Phase 2 must not start without explicit approval.

### Created application files

```text
apps/web/.gitignore
apps/web/.oxlintrc.json
apps/web/.prettierignore
apps/web/index.html
apps/web/package.json
apps/web/playwright.config.ts
apps/web/pnpm-lock.yaml
apps/web/pnpm-workspace.yaml
apps/web/public/favicon.svg
apps/web/README.md
apps/web/src/App.css
apps/web/src/App.test.tsx
apps/web/src/App.tsx
apps/web/src/contracts/assistantTurnPlan.test.ts
apps/web/src/contracts/assistantTurnPlan.ts
apps/web/src/features/avatar/avatarEngine.test.ts
apps/web/src/features/avatar/avatarEngine.ts
apps/web/src/features/avatar/ProceduralAvatar.tsx
apps/web/src/features/avatar/webgl.ts
apps/web/src/features/companion/types.ts
apps/web/src/features/companion/useCompanionController.ts
apps/web/src/features/providers/conversationProvider.ts
apps/web/src/features/providers/mockConversationProvider.test.ts
apps/web/src/features/providers/mockConversationProvider.ts
apps/web/src/index.css
apps/web/src/main.tsx
apps/web/src/shared/useReducedMotion.ts
apps/web/src/test/setup.ts
apps/web/tests/e2e/mobile.spec.ts
apps/web/tsconfig.app.json
apps/web/tsconfig.json
apps/web/tsconfig.node.json
apps/web/vite.config.ts
```

### Modified Phase 0 files

`README.md`, `docs/17-roadmap.md`, and `docs/22-requirements-traceability-matrix.md` were updated with implementation status/evidence. This review record is new. No other Phase 0 document or contract was changed.

### Removed scaffold-only files

Unused Vite template assets `public/icons.svg`, `src/assets/hero.png`, `src/assets/react.svg`, and `src/assets/vite.svg` were removed before review and were never part of a checkpoint.

### Validation evidence

```text
pnpm format:check  PASS
pnpm lint          PASS
pnpm typecheck     PASS
pnpm test          PASS — 14 tests
pnpm test:e2e      PASS — 8 tests, Pixel 5 + 320x568
pnpm build         PASS — manifest + service worker + 7 precache entries
pnpm audit --audit-level high PASS — 0 vulnerabilities
python scripts/validate_blueprint.py PASS
```

The app pins the locally validated package manager as `pnpm@11.7.0`. A targeted pnpm override moves `filelist` from vulnerable `minimatch@5.1.9`/`brace-expansion@2.1.3` to `minimatch@10.2.6`/patched `brace-expansion@5.0.8`; formatting, tests, PWA build and audit pass with the override. The dependency tree retains one upstream optional WASM peer warning from Vite 8.1.5 → Rolldown → `@napi-rs/wasm-runtime` requesting alpha `@emnapi` v2 peers while the stable tree resolves v1.11.1. The native Windows build, tests and browser runs pass. No speculative alpha dependency was added to hide that warning; recheck when Vite/Rolldown publishes a stable resolution.

## Alternatives considered

Using quarantined VRMs or downloading a new model would violate the asset gate. Adding provider SDKs now would exceed Phase 1 and create credential/cost risk.

## Reasoning

The procedural adapter proves state, performance, accessibility and degradation boundaries without coupling the UI to an unsafe asset or paid provider.

## Risks

- Procedural CSS is not evidence of real VRM loading, retargeting or Android GPU performance.
- Mock timings do not predict STT/LLM/TTS latency.
- Real microphone permissions, echo, barge-in audio and network behavior remain untested.
- PWA SVG icon acceptance may vary by store/browser; dedicated PNG icons should be created from original branding before release.
- Physical Android testing is still required; automated device emulation is not a hardware/thermal benchmark.

## Acceptance criteria

Phase 1 review passes when the owner verifies the Android LAN demo, accepts the procedural-placeholder deviation and explicitly authorizes the next phase. Until then, no FastAPI/provider/credential work begins.

## Exact local run command

```powershell
pnpm --dir apps/web dev --host 0.0.0.0
```
