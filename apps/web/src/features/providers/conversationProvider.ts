import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId } from "../companion/types";

export type ConversationProviderEvent =
  | { type: "thinking" }
  | { type: "text.delta"; delta: string }
  | { type: "plan"; plan: AssistantTurnPlan }
  | { type: "usage"; latencyMs: number };

export interface ConversationRequest {
  text: string;
  companionId: CompanionId;
  signal: AbortSignal;
  brainModel?: string;
}

export interface ConversationProvider {
  readonly id: string;
  readonly mode: "mock" | "local" | "groq" | "openai" | "custom" | "real";
  streamTurn(
    request: ConversationRequest,
  ): AsyncGenerator<ConversationProviderEvent>;
}
