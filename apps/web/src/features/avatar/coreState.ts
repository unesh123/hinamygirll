/**
 * coreState.ts — HINAA's crystalline core (near the collarbone) speaks her
 * real state through color, exactly as the owner specified:
 *
 *   cyan   = listening
 *   violet = reasoning
 *   blue   = speaking
 *   white  = local idle
 *   amber  = attention / confirmation required
 *   red    = genuine failure
 *
 * Kept framework-free so the mapping is unit-testable and reusable.
 */

export type CoreState =
  | "idle"
  | "listening"
  | "reasoning"
  | "speaking"
  | "attention"
  | "failure";

export interface CoreStateMeta {
  label: string;
  /** CSS-safe hex color shown by the core crystal + glow. */
  color: string;
  /** Verb phrase for tooltips / assistive text. */
  detail: string;
}

export const CORE_STATE_META: Record<CoreState, CoreStateMeta> = {
  idle: {
    label: "Idle",
    color: "#f1f5f9",
    detail: "Local idle — the core breathes softly.",
  },
  listening: {
    label: "Listening",
    color: "#22d3ee",
    detail: "Listening — soft cyan, quiet and attentive.",
  },
  reasoning: {
    label: "Reasoning",
    color: "#8b5cf6",
    detail: "Reasoning — violet, the iris ring brightens.",
  },
  speaking: {
    label: "Speaking",
    color: "#3b82f6",
    detail: "Speaking — blue, shaping words into light.",
  },
  attention: {
    label: "Attention",
    color: "#f59e0b",
    detail: "Attention — amber, confirmation or input needed.",
  },
  failure: {
    label: "Failure",
    color: "#ef4444",
    detail: "Failure — red, something genuinely went wrong.",
  },
};

export const CORE_STATES: CoreState[] = Object.keys(
  CORE_STATE_META,
) as CoreState[];

/**
 * Maps the simplified CompanionState (and the finer-grained experience
 * states it derives from) onto the six core states.
 */
export function coreStateFor(state: string): CoreState {
  switch (state) {
    case "listening":
    case "possible_speech":
    case "active_speech":
      return "listening";
    case "thinking":
    case "streaming_text":
    case "committing":
    case "transcribing":
    case "hesitation":
      return "reasoning";
    case "speaking":
      return "speaking";
    case "interrupted":
    case "paused":
    case "session_starting":
    case "session_ending":
      return "attention";
    case "error":
    case "provider_unavailable":
    case "reconnecting":
      return "failure";
    case "booting":
    case "intro":
    default:
      return "idle";
  }
}

/** True while the iris ring should be brighter (deep reasoning/remembering). */
export function irisRingActiveFor(state: string): boolean {
  return coreStateFor(state) === "reasoning";
}
