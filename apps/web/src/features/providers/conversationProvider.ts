import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId } from "../companion/types";

import type { ProviderMode } from "./types/provider";

export type ConversationProviderEvent =
  | { type: "thinking" }
  | { type: "text.delta"; delta: string }
  | { type: "plan"; plan: AssistantTurnPlan }
  | { type: "usage"; latencyMs: number };

export interface ConversationRequest {
  text: string;
  companionId: CompanionId;
  signal: AbortSignal;
  /** Active product locale resolved before provider routing. */
  language: "en-US" | "hi-IN" | "ne-NP";
  brainModel?: string;
}

export interface ConversationProvider {
  readonly id: string;
  readonly mode: ProviderMode;
  streamTurn(
    request: ConversationRequest,
  ): AsyncGenerator<ConversationProviderEvent>;
}
