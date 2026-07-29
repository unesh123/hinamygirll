import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";

export type CompanionState =
  "idle" | "listening" | "thinking" | "speaking" | "interrupted" | "error";

export type CompanionId = "hinaa" | "hiro";

export interface TranscriptMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  plan?: AssistantTurnPlan;
}

export const companionProfiles: Record<
  CompanionId,
  { name: string; label: string; greeting: string; accent: string }
> = {
  hinaa: {
    name: "Hinaa",
    label: "Warm & playful",
    greeting: "Namaste! Ma Hinaa ko mock mode ho. K kura test garne?",
    accent: "rose",
  },
  hiro: {
    name: "Hiro",
    label: "Calm & helpful",
    greeting: "Namaste! Ma Hiro ko mock mode ho. Ke test garau, bro?",
    accent: "indigo",
  },
};
