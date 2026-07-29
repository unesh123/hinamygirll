# ADR-002: PWA first

## Status
Accepted — 2026-07-30

## Context and purpose
Deliver mobile UX quickly with 3D/audio and a web-skilled workflow.

## Decision
React/TypeScript/Vite installable PWA first; Capacitor Android post-MVP.

## Alternatives considered
Native Kotlin/Compose and React Native improve OS integration but add avatar/audio integration and packaging work.

## Reasoning
PWA supports rapid iteration, shareable demo, Web Audio/WebGL and text fallback.

## Risks and consequences
iOS/background/media limitations and browser variation. Do not promise background assistant behavior; test target browsers; retain native migration seam.

## Acceptance criteria / revisit
Install/audio/WebGL work on target Android. Revisit when required OS APIs cannot be safely delivered by browsers.

