# ADR-006: Browser VRM engine

## Status
Accepted — 2026-07-30

## Context and purpose
Render two expressive anime-style avatars on mobile web.

## Decision
Three.js through React Three Fiber with `@pixiv/three-vrm`, VRM 1.0 target, VRMA/licensed clips plus procedural layers.

## Alternatives considered
Unity WebGL has strong animation tooling but large mobile payload/memory; Babylon.js is capable but three-vrm is the focused VRM ecosystem choice.

## Reasoning
Fits React client, current TypeScript package and required degradation controls.

## Risks and consequences
GPU/browser/device variability and VRM version differences. Enforce budgets and static/text fallback.

## Acceptance criteria / revisit
Target phones sustain low tier >=30 FPS. Revisit engine only after a prototype benchmark demonstrates a blocker.

