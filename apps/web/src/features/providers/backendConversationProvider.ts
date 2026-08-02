import { parseAssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type {
  ConversationProvider,
  ConversationProviderEvent,
  ConversationRequest,
} from "./conversationProvider";

type ProviderMode = "mock" | "local" | "groq" | "openai" | "custom" | "real";

interface StreamEvent {
  type: "thinking" | "text.delta" | "plan" | "usage" | "error";
  delta?: string;
  plan?: unknown;
  code?: string;
  message?: string;
  latencyMs?: number;
}

export class BackendConversationProvider implements ConversationProvider {
  readonly id: string;
  readonly mode: ProviderMode;

  constructor(mode: ProviderMode) {
    this.mode = mode;
    this.id = `hinaa-api-${mode}`;
  }

  async *streamTurn(
    request: ConversationRequest,
  ): AsyncGenerator<ConversationProviderEvent> {
    const payload: {
      sessionId: string;
      text: string;
      companionId: ConversationRequest["companionId"];
      language: "mixed";
      providerMode: ProviderMode;
      brainModel?: string;
    } = {
      sessionId: "browser-session",
      text: request.text,
      companionId: request.companionId,
      language: "mixed",
      providerMode: this.mode,
    };
    if (
      (this.mode === "openai" ||
        this.mode === "custom" ||
        this.mode === "real") &&
      request.brainModel
    ) {
      payload.brainModel = request.brainModel;
    }
    const response = await fetch("/api/v1/conversations/turns:stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: request.signal,
    });
    if (!response.ok || !response.body) {
      throw new Error(`Backend request failed (${response.status})`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line) as StreamEvent;
          if (event.type === "thinking") yield { type: "thinking" };
          if (event.type === "text.delta" && event.delta)
            yield { type: "text.delta", delta: event.delta };
          if (event.type === "plan" && event.plan)
            yield { type: "plan", plan: parseAssistantTurnPlan(event.plan) };
          if (event.type === "usage" && Number.isFinite(event.latencyMs))
            yield { type: "usage", latencyMs: event.latencyMs ?? 0 };
          if (event.type === "error")
            throw new Error(
              `${event.code ?? "BACKEND_ERROR"}: ${event.message ?? "Request failed"}`,
            );
        }
        if (done) break;
      }
    } finally {
      reader.releaseLock();
    }
  }
}
