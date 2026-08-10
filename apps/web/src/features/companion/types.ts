import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";

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

export type CompanionState =
  | "idle" | "listening" | "thinking" | "speaking" | "interrupted" | "error";

export type CompanionId = "hinaa" | "hiro";

export interface TranscriptMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  /** ISO-8601 string set when the message is created. Never at render time. */
  createdAt: string;
  plan?: AssistantTurnPlan;
  toolActivity?: Array<{ status: string; label: string; id: string }>;
  toolResults?: Array<{ toolName: string; result: any }>;
}

export const companionProfiles: Record<
  CompanionId,
  { name: string; label: string; greeting: string; accent: string }
> = {
  hinaa: {
    name: "HINAA",
    label: "Intelligent assistant",
    greeting:
      "Hello Unesh! Main tumhare liye ready hoon. Aap mujhse baat kar sakte ho, ya yahaan text bhi kar sakte ho. What would you like to do?",
    accent: "mint",
  },
  hiro: {
    name: "Hiro",
    label: "Calm & helpful",
    greeting: "Hello Unesh! I'm Hiro. Talk or type—I'm ready to help you.",
    accent: "indigo",
  },
};
