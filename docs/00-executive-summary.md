# Executive summary

## Purpose

Define an achievable final-year version of HINAA and separate it from the commercial vision.

## Decision

Build a vertically sliced PWA demo around one compelling loop: tap microphone, receive partial Nepali/code-switched transcript, obtain a concise response, hear Nepali speech, and see a synchronized VRM performance. Text and a no-key mock provider always remain available. Two companion profiles share one engine but have separate identity, voice, and personality settings.

The MVP is a modular monolith, not a fleet of services. FastAPI owns authentication, orchestration, provider routing, memory consent, schema validation, and audit records. The PWA owns capture/playback, presentation, avatar rendering, local interruption, and accessible fallback. PostgreSQL is the system of record; Redis is optional.

## Alternatives considered

- Native Android first: stronger device integration, but slows a web-skilled solo student and weakens rapid iteration.
- One realtime vendor for everything: lower initial integration effort, but weakens Nepali benchmarking and portability.
- Microservices: independently scalable, but operationally excessive for a one-student MVP.
- Fully local models: better privacy, but ordinary student hardware cannot guarantee useful multilingual quality and latency.

## Reasoning

The design minimizes simultaneous unknowns, preserves provider choice, supports a no-cost demo, and makes the academic contribution measurable. A cascade voice path is the reliable MVP baseline; provider-direct realtime is an experiment behind the same event protocol.

## Risks

Nepali/code-switch speech quality, browser audio behavior, mobile 3D performance, asset licensing, changing provider quotas, and an overlarge scope remain the largest risks. Each has an early benchmark, fallback, or scope cut in the roadmap.

## Acceptance criteria

- Every MVP requirement maps to an owner component, phase, and test.
- Demo works in mock/text-only mode when providers, WebGL, or network fail.
- No secret or unapproved memory reaches client bundles, logs, or source control.
- Phase 1 implementation does not start without explicit approval.

## Verified sources (2026-07-30)

- [Gemini models and pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini available regions](https://ai.google.dev/gemini-api/docs/available-regions)
- [Azure Speech language and voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)
- [Azure for Students](https://azure.microsoft.com/en-us/free/students)

