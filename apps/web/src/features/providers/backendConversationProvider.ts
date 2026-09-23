import { parseAssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import { hinaaIdentityHeaders } from "../../lib/hinaaIdentity";
import { describeCode, describeResponseFailure, describeThrownFailure, singleLine, TurnFailure } from "../../lib/turnFailure";
import type {
  AgentRuntimeEvent,
  ConversationProvider,
  ConversationProviderEvent,
  ConversationRequest,
} from "./conversationProvider";

import type { ProviderMode } from "./types/provider";

interface StreamEvent {
  type: string;
  delta?: string;
  plan?: unknown;
  code?: string;
  message?: string;
  retryable?: boolean;
  latencyMs?: number;
  event?: unknown;
  runId?: string;
  stepId?: string | null;
  query?: string;
  sourcesCount?: number;
}

function normalizeAgentEvent(event: StreamEvent): AgentRuntimeEvent | null {
  if (!event.type.startsWith("agent.") && event.type !== "confirmation.required") return null;
  const raw = event.event;
  if (raw && typeof raw === "object") {
    const candidate = raw as Record<string, unknown>;
    if (typeof candidate.event_type === "string" && typeof candidate.run_id === "string") {
      return {
        event_id: typeof candidate.event_id === "string" ? candidate.event_id : undefined,
        sequence: typeof candidate.sequence === "number" ? candidate.sequence : 0,
        event_type: candidate.event_type,
        timestamp: typeof candidate.timestamp === "string" ? candidate.timestamp : undefined,
        run_id: candidate.run_id,
        conversation_id: typeof candidate.conversation_id === "string" ? candidate.conversation_id : null,
        step_id: typeof candidate.step_id === "string" ? candidate.step_id : null,
        payload:
          candidate.payload && typeof candidate.payload === "object"
            ? (candidate.payload as Record<string, unknown>)
            : {},
      };
    }
  }
  if (typeof event.runId !== "string") return null;
  return {
    sequence: 0,
    event_type: event.type,
    run_id: event.runId,
    step_id: event.stepId ?? null,
    payload: {},
  };
}

export class BackendConversationProvider implements ConversationProvider {
  private readonly fallbackSessionId = globalThis.crypto.randomUUID();
  readonly id: string;
  readonly mode: ProviderMode;

  constructor(mode: ProviderMode) {
    this.mode = mode;
    this.id = `hinaa-api-${mode}`;
  }

  async *streamTurn(
    request: ConversationRequest,
  ): AsyncGenerator<ConversationProviderEvent> {
    const convId = request.conversationId ?? request.sessionId ?? this.fallbackSessionId;
    const payload: Record<string, any> = {
      sessionId: convId,
      conversationId: convId,
      text: request.text,
      companionId: request.companionId,
      language: request.language,
      providerMode: this.mode,
    };
    if (request.responseMode) {
      payload.responseMode = request.responseMode;
    }
    if (request.imageUrl) {
      payload.imageUrl = request.imageUrl;
    }
    if (request.attachment_ids && request.attachment_ids.length > 0) {
      payload.attachment_ids = request.attachment_ids;
    }
    if (request.attachments && request.attachments.length > 0) {
      payload.attachments = request.attachments;
    }
    if (request.reference_images && request.reference_images.length > 0) {
      payload.reference_images = request.reference_images;
    }
    if (request.imageEngine) {
      payload.imageEngine = request.imageEngine;
    }
    if (request.voiceEngine) {
      payload.voiceEngine = request.voiceEngine;
    }
    if (
      (this.mode === "openai" ||
        this.mode === "custom" ||
        this.mode === "claude" ||
        this.mode === "qwen" ||
        this.mode === "agent-router" ||
        this.mode === "cx-gateway" ||
        this.mode === "codecraft" ||
        this.mode === "real") &&
      request.brainModel
    ) {
      payload.brainModel = request.brainModel;
    }
    const apiBase = import.meta.env.VITE_HINAA_API_BASE_URL
      ? String(import.meta.env.VITE_HINAA_API_BASE_URL).replace(/\/+$/, "")
      : "";
    const streamUrl = `${apiBase}/api/v1/conversations/turns:stream`;

    let response: Response;
    try {
      response = await fetch(streamUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "bypass-tunnel-reminder": "true",
          ...hinaaIdentityHeaders(),
        },
        body: JSON.stringify(payload),
        signal: request.signal,
      });
    } catch (netErr: any) {
      if (request.signal?.aborted) throw netErr;
      throw new TurnFailure(
        describeThrownFailure(netErr, "HINAA's API never answered"),
      );
    }

    const contentType = response.headers.get("content-type");
    // A 200 whose body is HTML is an edge error page: the tunnel or a proxy
    // answered, not HINAA, and only the content type proves it.
    if (!response.ok || !response.body || (contentType ?? "").toLowerCase().includes("text/html")) {
      const errText = response.body ? await response.text().catch(() => "") : "";
      throw new TurnFailure(
        describeResponseFailure({
          status: response.status,
          body: errText,
          contentType,
        }),
        { status: response.status },
      );
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let lastSeenSequence = -1;
    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let event: StreamEvent;
          try {
            event = JSON.parse(line) as StreamEvent;
          } catch {
            // The stream is NDJSON by contract, so anything else was written by
            // something between here and HINAA. Report the layer, not the bytes.
            throw new TurnFailure(
              describeResponseFailure({
                status: response.status,
                body: line,
                contentType,
              }),
              { status: response.status },
            );
          }
          const agentEvent = normalizeAgentEvent(event);
          if (agentEvent) yield { type: "agent.event", event: agentEvent };
          if (event.type === "thinking") yield { type: "thinking" };
          if (event.type === "search.started")
            yield { type: "search.started", query: event.query || "" };
          if (event.type === "search.completed")
            yield { type: "search.completed", query: event.query || "", sourcesCount: event.sourcesCount };
          if (event.type === "text.delta" && event.delta) {
            const rawEvent = event as unknown as Record<string, unknown>;
            if (typeof rawEvent.sequence === "number") {
              if (rawEvent.sequence <= lastSeenSequence) {
                continue;
              }
              lastSeenSequence = rawEvent.sequence;
            }
            yield { type: "text.delta", delta: event.delta };
          }
          if (event.type === "plan" && event.plan) {
            let plan: any;
            try {
              plan = parseAssistantTurnPlan(event.plan);
            } catch (err) {
              console.warn("Recovering from plan schema divergence:", err);
              const raw = event.plan as any;
              plan = {
                schemaVersion: 1,
                spokenText: typeof raw.spokenText === "string" ? raw.spokenText : (typeof raw.displayText === "string" ? raw.displayText.slice(0, 140) : "I'm right here."),
                displayText: typeof raw.displayText === "string" ? raw.displayText : (typeof raw.text === "string" ? raw.text : "I'm right here."),
                language: raw.language === "hi-IN" ? "hi-IN" : raw.language === "en-US" ? "en-US" : "mixed",
                emotion: { primary: "neutral", intensity: 0.5, valence: 0.5, arousal: 0.5 },
                performance: { facePreset: "neutral", gesture: "none", gazeTarget: "camera", headMotion: "none", blinkRate: 0.5 },
                memoryCandidates: Array.isArray(raw.memoryCandidates) ? raw.memoryCandidates : [],
                toolRequests: Array.isArray(raw.toolRequests) ? raw.toolRequests : [],
              };
            }
            yield { type: "plan", plan };
          }
          if (event.type === "usage" && Number.isFinite(event.latencyMs))
            yield { type: "usage", latencyMs: event.latencyMs ?? 0 };
          if (event.type === "error") {
            // The code routes recovery; only the sentence belongs in the bubble.
            throw new TurnFailure(
              describeCode(event.code, event.message) ||
                singleLine(event.message, "HINAA reported an error on this turn."),
              { code: event.code, retryable: event.retryable },
            );
          }
        }
        if (done) break;
      }
    } finally {
      reader.releaseLock();
    }
  }
}
