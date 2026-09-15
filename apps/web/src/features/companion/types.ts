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
  | "idle"
  | "listening"
  | "understanding"
  | "thinking"
  | "researching"
  | "using_tool"
  | "generating"
  | "writing"
  | "waiting"
  | "speaking"
  | "success"
  | "confused"
  | "error"
  | "interrupted";

export type CompanionId = "hinaa" | "hiro";

export interface MessageAttachment {
  asset_id?: string;
  assetId?: string;
  kind?: "image" | "document" | "spreadsheet" | "text" | "code" | "audio" | "video" | "archive";
  mime_type?: string;
  mimeType?: string;
  filename?: string;
  size_bytes?: number;
  sizeBytes?: number;
  sha256?: string;
  ordinal?: number;
  role?: string | null;
  url?: string | null;
}

export interface TranscriptMessage {
  id: string;
  role: "user" | "assistant";
  conversationId?: string;
  text: string;
  /** ISO-8601 string set when the message is created. Never at render time. */
  createdAt: string;
  /** Canonical serialized assistant turn; legacy messages retain plain text. */
  content?: string;
  plan?: AssistantTurnPlan;
  toolActivity?: Array<{ status: string; label: string; id: string }>;
  toolResults?: Array<{ toolName: string; result: any }>;
  imageUrl?: string | null;
  attachments?: MessageAttachment[];
  requestedProvider?: string | null;
  requestedModel?: string | null;
  resolvedProvider?: string | null;
  resolvedModel?: string | null;
  fallback?: boolean;
  fallbackReason?: string | null;
  latencyMs?: number | null;
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
