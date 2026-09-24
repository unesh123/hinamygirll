import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId } from "../companion/types";

import type { ProviderMode } from "./types/provider";

export type ConversationProviderEvent =
  | { type: "thinking" }
  | { type: "text.delta"; delta: string }
  | { type: "plan"; plan: AssistantTurnPlan }
  | { type: "usage"; latencyMs: number }
  | { type: "agent.event"; event: AgentRuntimeEvent }
  | { type: "search.started"; query: string }
  | { type: "search.completed"; query: string; sourcesCount?: number }
  | { type: "astra.route"; route: string; confidence: number; goal: string; candidates: string[] }
  | { type: "astra.entity"; canonicalName: string; groundedQuery: string }
  | { type: "astra.tool"; status: "started" | "progress" | "completed" | "failed"; toolName: string; toolRunId: string; message?: string; parameters?: any };

export interface AgentRuntimeEvent {
  event_id?: string;
  sequence: number;
  event_type: string;
  timestamp?: string;
  run_id: string;
  conversation_id?: string | null;
  step_id?: string | null;
  payload?: Record<string, unknown>;
}

/** Mirrors the `ResponseMode` Literal in apps/api/hinaa_api/models.py. */
export type ResponseMode =
  | "conversation"
  | "professional"
  | "technical"
  | "research"
  | "automation"
  | "academic"
  | "creative"
  | "concise_voice";

export interface ConversationRequest {
  text: string;
  companionId: CompanionId;
  signal: AbortSignal;
  /** Active product locale resolved before provider routing. */
  language: "en-US" | "hi-IN" | "ne-NP" | "mixed";
  /** Omitted lets the backend infer the mode from the text. */
  responseMode?: ResponseMode;
  sessionId?: string;
  conversationId?: string;
  brainModel?: string;
  imageEngine?: string;
  voiceEngine?: string;
  imageUrl?: string;
  attachment_ids?: string[];
  reference_images?: string[];
  attachments?: import("../companion/types").MessageAttachment[];
}

export interface ConversationProvider {
  readonly id: string;
  readonly mode: ProviderMode;
  streamTurn(
    request: ConversationRequest,
  ): AsyncGenerator<ConversationProviderEvent>;
}
