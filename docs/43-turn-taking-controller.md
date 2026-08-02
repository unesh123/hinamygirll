# 43 — Turn-taking controller

## Purpose

Hands-free live conversation without a per-turn mic/send button after the user
explicitly starts an active session and grants microphone permission.

## States

`inactive`, `initializing`, `listening`, `possible_speech`, `active_speech`,
`hesitation`, `possible_end_of_turn`, `committing`, `waiting_for_provider`,
`speaking`, `interrupted`, `reconnecting`, `provider_unavailable`,
`microphone_denied`, `error`.

## Signals combined

- Audio energy
- Speech / silence frame counts
- STT partial completeness heuristics
- Playback state (barge-in)
- Pause / end session
- Duplicate-final fingerprint suppression

Defaults are safe starting points, not claimed perfect.

## Required behaviors

- Short hesitation must not always end the turn.
- Long silence ends the turn when speech was meaningful.
- Empty / noise-only audio without transcript does not answer.
- Duplicate finals do not duplicate replies.
- Speech during playback interrupts immediately.
- Pause and stop are always available; mic is never silent-always-on.
