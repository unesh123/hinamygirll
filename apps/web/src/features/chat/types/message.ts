/**
 * ChatMessage — production-grade typed message model.
 *
 * createdAt is stored at message creation time, never at render time.
 * All fields are required or explicitly optional to prevent silent gaps.
 */

import type { AssistantTurnPlan } from "../../../contracts/assistantTurnPlan";

export type MessageRole = "user" | "assistant" | "system";

export type MessageStatus =
  | "queued"
  | "sending"
  | "streaming"
  | "complete"
  | "failed"
  | "cancelled";

export interface MessageError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface ChatMessage {
  /** UUID generated at message creation — never at render time. */
  id: string;
  conversationId: string;
  role: MessageRole;
  /** Full rendered text. For streaming messages, grows incrementally. */
  content: string;
  /** ISO-8601 string set once when the message object is created. */
  createdAt: string;
  /** Updated when content changes (streaming). */
  updatedAt?: string;
  status: MessageStatus;
  /** For assistant messages: the full structured plan from the backend. */
  plan?: AssistantTurnPlan;
  /** Which backend provider handled this turn. */
  provider?: string;
  /** Which model was used. */
  model?: string;
  /** End-to-end latency in milliseconds. */
  latencyMs?: number;
  /** Error payload present only when status === 'failed'. */
  error?: MessageError;
  /** Activity stream for tools running during this message */
  toolActivity?: Array<{ status: string; label: string; id: string }>;
  /** Completed results from tools */
  toolResults?: Array<{ toolName: string; result: any }>;
}

/** Create a new user message with a correct creation timestamp. */
export function createUserMessage(
  content: string,
  conversationId: string,
): ChatMessage {
  return {
    id: crypto.randomUUID(),
    conversationId,
    role: "user",
    content,
    createdAt: new Date().toISOString(),
    status: "complete",
  };
}

/** Create a pending assistant message placeholder that will be filled by streaming. */
export function createAssistantPlaceholder(
  conversationId: string,
): ChatMessage {
  return {
    id: crypto.randomUUID(),
    conversationId,
    role: "assistant",
    content: "",
    createdAt: new Date().toISOString(),
    status: "streaming",
  };
}

/** Format a message creation timestamp as a short locale time string. */
export function formatMessageTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}
