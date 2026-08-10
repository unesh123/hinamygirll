# 70: Experience State Machine Specification

## 1. HinaaExperienceState Typed Definition
```typescript
export type HinaaExperienceState =
  | "booting"
  | "intro"
  | "idle"
  | "session_starting"
  | "listening"
  | "possible_speech"
  | "active_speech"
  | "hesitation"
  | "committing"
  | "transcribing"
  | "thinking"
  | "streaming_text"
  | "speaking"
  | "interrupted"
  | "reconnecting"
  | "provider_unavailable"
  | "paused"
  | "session_ending"
  | "error";
```
