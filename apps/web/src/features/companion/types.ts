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
    greeting:
      "Namaste! Hinaa ready cha. Real voice mode ready bhaye Talk to Hinaa थिच्नु, natra text bata test garna milcha.",
    accent: "rose",
  },
  hiro: {
    name: "Hiro",
    label: "Calm & helpful",
    greeting: "Namaste! Hiro ready cha. Talk or type—ma help garna ready chu.",
    accent: "indigo",
  },
};
