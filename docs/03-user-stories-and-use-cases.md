# User stories and use cases

## Purpose

Turn product scope into observable user behavior.

## Decision

| ID | User story | Main success condition |
|---|---|---|
| US-01 | As a Nepali user, I speak naturally in Devanagari/Romanized/code-switching. | Partial and final transcript remain editable and preserve meaning. |
| US-02 | I type when speech or network is unreliable. | Same orchestration path; no microphone required. |
| US-03 | I switch female/male companions. | Profile, voice and avatar change; history remains user-owned. |
| US-04 | I interrupt speech. | Audio stops locally, turn is cancelled, state becomes interrupted/listening. |
| US-05 | I explicitly save, inspect, edit or forget a memory. | No long-term write occurs before confirmation. |
| US-06 | I use HINAA without keys. | Mock mode completes the full UI/avatar loop offline. |
| US-07 | I use a weak phone or no WebGL. | Quality falls back to low/static/text without losing chat controls. |
| US-08 | I understand provider failure. | A concise explanation and safe fallback are shown. |
| US-09 | I opt into one camera analysis request. | Just-in-time permission, persistent indicator, one-tap stop, no identity inference. |
| US-10 | I adjust personality and language mix. | Bounded settings affect style but not safety or accuracy. |

### Primary voice use case

Precondition: authenticated or local-demo session; camera off; microphone not yet active. User taps mic, grants permission, and speaks. Client emits microphone state and audio; STT emits partial/final text; orchestrator selects provider; validated `AssistantTurnPlan` streams; TTS audio and performance cues play against a shared clock. Barge-in cancels all downstream work. History persists only under the selected privacy mode.

### Failure extensions

Permission denied opens text input; STT mismatch offers transcript correction; LLM/TTS failure uses text/mock fallback; avatar failure uses portrait; network loss queues no sensitive audio and offers retry.

## Alternatives considered

Always-listening wake words and automatic memory were rejected because they conflict with privacy and final-year scope.

## Reasoning

These stories cover the demo-critical happy path, user agency, and graceful degradation.

## Risks

Browser permission prompts vary by platform. Test Chrome Android plus one secondary supported browser and document exceptions.

## Acceptance criteria

Each story has at least one end-to-end test and a user-visible failure route.

