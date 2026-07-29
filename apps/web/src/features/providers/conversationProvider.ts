import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId } from "../companion/types";

export type ConversationProviderEvent =
  | { type: "thinking" }
  | { type: "text.delta"; delta: string }
  | { type: "plan"; plan: AssistantTurnPlan };

export interface ConversationRequest {
  text: string;
  companionId: CompanionId;
  signal: AbortSignal;
}

export interface ConversationProvider {
  readonly id: string;
  readonly mode: "mock";
  streamTurn(
    request: ConversationRequest,
  ): AsyncGenerator<ConversationProviderEvent>;
}
