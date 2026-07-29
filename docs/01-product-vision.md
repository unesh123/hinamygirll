# Product vision

## Purpose

Describe whom HINAA serves, how it behaves, and what it must never become.

## Decision

HINAA serves Nepali users who may prefer Devanagari, Romanized Nepali, English, Hindi, or mixtures. It gives short action-oriented answers by default and expands on request. Voice is central, text is dependable fallback, and a responsive original anime-style avatar makes conversational state legible rather than pretending to be human.

Both companions are warm, playful, bounded, and transparent about uncertainty. User sliders configure affection, sass, energy, humor, formality, response length, proactivity, and language mix within immutable safety limits. HINAA never claims consciousness or physical presence, diagnoses emotion, pressures the user to stay, discourages real relationships, or invents certainty.

## Alternatives considered

- English-first localization would be easier but fails the primary audience.
- Unbounded role-play would feel flexible but creates manipulation, safety, and evaluation problems.
- A static chat UI is easier but does not test the project’s avatar-performance research question.

## Reasoning

Language accessibility and explicit boundaries are product features, not later compliance tasks. The avatar adds academic value only when its timing and performance can be evaluated against a non-avatar control.

## Risks

Personality controls can drift into dependency cues; code-switching can be normalized incorrectly; cute visual design can obscure privacy state. Mitigate with immutable policy tests, preserve-original transcript display, and persistent microphone/camera indicators.

## Acceptance criteria

- Representative users can select language, response length, companion, voice speed, reduced motion, and text-only mode.
- Responses preserve user intent across the supported language mixes.
- Boundary regression tests pass for manipulation, false personhood, unsupported claims, and emotional overreach.

