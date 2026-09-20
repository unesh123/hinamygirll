import { useCallback, useEffect, useRef, useState } from "react";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import { BackendConversationProvider } from "../providers/backendConversationProvider";
import type {
  AgentRuntimeEvent,
  ResponseMode,
} from "../providers/conversationProvider";
import { MockConversationProvider } from "../providers/mockConversationProvider";
import {
  companionProfiles,
  type CompanionId,
  type CompanionState,
  type TranscriptMessage,
} from "./types";
import type { ProviderRuntimeSelection } from "../providers/utils/resolveProviderSelection";
import type { ActiveLanguagePolicy } from "../settings/types/settings";
import { resolveToolOutcome } from "../tools/toolOutcome";
import {
  deserializeAssistantTurn,
  getAssistantDisplayText,
  getSafeAssistantStreamingText,
  serializeAssistantTurn,
} from "./assistantTurnCodec";
import {
  loadConversationMessages,
  saveConversationMessages,
} from "./sessionManager";

function createId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ?? `mock-${Date.now()}-${Math.random()}`
  );
}

function restoreMessages(raw: unknown): TranscriptMessage[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  return raw.filter((item): item is TranscriptMessage => !!item && typeof item === "object")
    .map((message) => {
      if (message.role !== "assistant" || !message.content) return message;
      const plan = deserializeAssistantTurn(message.content);
      return plan
        ? { ...message, text: getAssistantDisplayText(message.content), plan }
        : message;
    });
}

function createMessage(
  role: "user" | "assistant",
  text: string,
  extra?: Partial<TranscriptMessage>,
): TranscriptMessage {
  return {
    id: createId(),
    role,
    text,
    createdAt: new Date().toISOString(),
    ...extra,
  };
}

export interface LiveAgentStep {
  id: string;
  label: string;
  status: "pending" | "active" | "done" | "error" | "cancelled";
  detail?: string;
}

function runtimeEventToSteps(
  previous: LiveAgentStep[],
  event: AgentRuntimeEvent,
): LiveAgentStep[] {
  const payload = event.payload ?? {};
  const stepId = event.step_id ?? "runtime";
  const title =
    typeof payload.title === "string"
      ? payload.title
      : event.event_type.replace(/^agent\./, "").replace(/\./g, " ");
  const message =
    typeof payload.message === "string"
      ? payload.message
      : typeof payload.code === "string"
        ? payload.code
        : undefined;
  const upsert = (step: LiveAgentStep) => {
    const existing = previous.findIndex((item) => item.id === step.id);
    if (existing === -1) return [...previous, step];
    const next = [...previous];
    next[existing] = { ...next[existing], ...step };
    return next;
  };

  if (event.event_type === "agent.run.created") {
    return upsert({
      id: "run",
      label: "Run accepted",
      status: "done",
      detail: "Server created a durable agent run",
    });
  }
  if (event.event_type === "agent.run.started" || event.event_type === "agent.planning.started") {
    return upsert({
      id: "plan",
      label: "Plan live turn",
      status: "active",
      detail: "HINAA is preparing a bounded runtime plan",
    });
  }
  if (event.event_type === "agent.plan.ready") {
    return upsert({
      id: "plan",
      label: "Plan ready",
      status: "done",
      detail: "Runtime validated the execution plan",
    });
  }
  if (event.event_type === "agent.step.started") {
    return upsert({ id: stepId, label: title, status: "active", detail: "Running through server runtime" });
  }
  if (event.event_type === "agent.step.progress") {
    return upsert({ id: stepId, label: title, status: "active", detail: message ?? "Runtime step updated" });
  }
  if (event.event_type === "agent.step.completed") {
    return upsert({ id: stepId, label: title, status: "done", detail: "Runtime step completed" });
  }
  if (event.event_type === "agent.step.failed") {
    return upsert({ id: stepId, label: title, status: "error", detail: message ?? "Runtime step failed" });
  }
  if (event.event_type === "confirmation.required") {
    return upsert({ id: stepId, label: title, status: "pending", detail: "Waiting for your approval" });
  }
  if (event.event_type === "agent.run.completed") {
    return previous.map((step) => ({ ...step, status: step.status === "error" ? step.status : "done" }));
  }
  if (event.event_type === "agent.run.failed") {
    return upsert({ id: "run", label: "Run needs attention", status: "error", detail: message ?? "Runtime failed safely" });
  }
  if (event.event_type === "agent.run.recovered") {
    return upsert({ id: "run", label: "Recovery requested", status: "active", detail: "Runtime restored recoverable work" });
  }
  if (event.event_type === "agent.run.cancelled" || event.event_type === "turn.cancelled") {
    return previous.map((step) => ({ ...step, status: step.status === "done" ? step.status : "cancelled" }));
  }
  return previous;
}

export interface CompanionController {
  companionId: CompanionId;
  switchCompanion: (id: CompanionId) => void;
  resetConversation: (newId?: string) => void;
  state: CompanionState;
  messages: TranscriptMessage[];
  setMessages: React.Dispatch<React.SetStateAction<TranscriptMessage[]>>;
  partialTranscript: string;
  streamingText: string;
  routing: ProviderRuntimeSelection;
  activePlan?: AssistantTurnPlan;
  agentSteps: LiveAgentStep[];
  isSearching: boolean;
  searchQuery: string;
  currentAgentRunId?: string;
  currentAgentConfirmationStepId?: string;
  cancelCurrentAgentRun: () => Promise<void>;
  resumeCurrentAgentRun: () => Promise<void>;
  confirmCurrentAgentStep: (approved: boolean) => Promise<void>;
  recoverCurrentAgentRun: () => Promise<void>;
  sendText: (
    text: string,
    options?: {
      forceBackend?: boolean;
      responseMode?: ResponseMode;
      imageUrl?: string;
      attachment_ids?: string[];
      attachments?: import("./types").MessageAttachment[];
      imageEngine?: string;
      voiceEngine?: string;
    },
  ) => Promise<
    { turnId: string; plan: AssistantTurnPlan; providerLatencyMs?: number } | undefined
  >;
  startMockListening: () => void;
  beginListening: () => void;
  stop: () => void;
  applyLivePartial: (text: string) => void;
  applyLiveFinal: (text: string) => void;
  applyLiveDelta: (delta: string) => void;
  applyLivePlan: (plan: AssistantTurnPlan) => void;
  applyLiveError: (message: string) => void;
  resolveToolRequest: (
    messageId: string,
    request: AssistantTurnPlan["toolRequests"][number],
    approved: boolean,
  ) => Promise<void>;
  setLiveState: (state: CompanionState) => void;
}

export interface CompanionControllerOptions {
  conversationId?: string | null;
  routing: ProviderRuntimeSelection;
  languagePolicy: ActiveLanguagePolicy;
  /**
   * Standing consent for tool execution. When true, proposed actions run
   * immediately instead of waiting for a per-action approval click. Defaults to
   * false so any caller that does not opt in keeps the explicit approval gate.
   */
  autoRunTools?: boolean;
}

function resolveTurnLanguage(text: string, policy: ActiveLanguagePolicy): "en-US" | "hi-IN" {
  if (policy === "hi-IN") return "hi-IN";
  if (policy === "en-US") return "en-US";
  return /[\u0900-\u097F]/.test(text) ? "hi-IN" : "en-US";
}

export function useCompanionController({ conversationId, routing, languagePolicy, autoRunTools = false }: CompanionControllerOptions): CompanionController {
  const [companionId, setCompanionId] = useState<CompanionId>("hinaa");
  const [state, setState] = useState<CompanionState>("idle");
  const [agentSteps, setAgentSteps] = useState<LiveAgentStep[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentAgentRunId, setCurrentAgentRunId] = useState<string>();
  const [currentAgentConfirmationStepId, setCurrentAgentConfirmationStepId] = useState<string>();
  const effectiveKey = conversationId ? `hinaa-messages-${conversationId}` : `hinaa-messages-${companionId}`;
  const [messages, setMessages] = useState<TranscriptMessage[]>(() => {
    try {
      const storedMessages = conversationId
        ? loadConversationMessages(conversationId)
        : (() => {
            const stored = localStorage.getItem(effectiveKey);
            return stored ? restoreMessages(JSON.parse(stored)) : null;
          })();
      const restored = restoreMessages(storedMessages);
      if (restored && restored.length > 0) return restored;
    } catch {}
    return [createMessage("assistant", companionProfiles.hinaa.greeting)];
  });

  const prevConvoIdRef = useRef(conversationId);
  useEffect(() => {
    if (prevConvoIdRef.current !== conversationId) {
      prevConvoIdRef.current = conversationId;
      try {
        const storedMessages = conversationId
          ? loadConversationMessages(conversationId)
          : (() => {
              const stored = localStorage.getItem(`hinaa-messages-${companionId}`);
              return stored ? restoreMessages(JSON.parse(stored)) : null;
            })();
        const restored = restoreMessages(storedMessages);
        if (restored && restored.length > 0) {
          setMessages(restored);
          return;
        }
      } catch {}
      setMessages([createMessage("assistant", companionProfiles[companionId]?.greeting ?? companionProfiles.hinaa.greeting)]);
    }
  }, [conversationId, companionId]);

  useEffect(() => {
    const key = conversationId ? `hinaa-messages-${conversationId}` : `hinaa-messages-${companionId}`;
    if (conversationId) saveConversationMessages(conversationId, messages);
    else localStorage.setItem(key, JSON.stringify(messages));
  }, [messages, conversationId, companionId]);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [activePlan, setActivePlan] = useState<AssistantTurnPlan>();
  const provider = useRef(new MockConversationProvider());
  const currentAbort = useRef<AbortController | undefined>(undefined);
  const timers = useRef<number[]>([]);
  const processedToolMessageIds = useRef<Set<string>>(new Set());
  // Confirmation-gated actions must be idempotent at the interaction layer.
  // A double click, touch event replay, or a transient rerender may not submit
  // the same external request twice or append duplicate terminal result cards.
  const resolvingToolRequestIds = useRef<Set<string>>(new Set());
  const turnSequence = useRef(0);
  const activeTurnId = useRef<string | null>(null);
  const finalizedTurnIds = useRef<Set<string>>(new Set());

  const clearTimers = useCallback(() => {
    for (const timer of timers.current) window.clearTimeout(timer);
    timers.current = [];
  }, []);

  type TurnFinalization = { errorText?: string; preservePartial?: boolean };

  // This is the sole terminal path for browser-chat turns. It is intentionally
  // idempotent and sequence-aware: a stale response cannot unlock, overwrite,
  // or append an error to a newer turn, while every active failure clears all
  // composer-blocking state immediately.
  const finalizeTurn = useCallback((turnId: string, result: TurnFinalization = {}) => {
    if (finalizedTurnIds.current.has(turnId) || activeTurnId.current !== turnId) return false;
    finalizedTurnIds.current.add(turnId);
    if (finalizedTurnIds.current.size > 96) finalizedTurnIds.current.clear();
    activeTurnId.current = null;
    currentAbort.current = undefined;
    clearTimers();
    if (!result.preservePartial) setPartialTranscript("");
    setStreamingText("");
    setActivePlan(undefined);
    const errorText = result.errorText;
    if (errorText) {
      setMessages((current) => [...current, createMessage("assistant", errorText)]);
    }
    setState("idle");
    return true;
  }, [clearTimers]);

  // Switching companion starts a fresh log with their own greeting, clears
  // any in-flight turn, and returns the stage to idle. Re-selecting the
  // already-active companion is a no-op — the transcript is left untouched.
  const switchCompanion = useCallback(
    (id: CompanionId) => {
      if (id === companionId) return;
      const previousTurn = activeTurnId.current;
      currentAbort.current?.abort();
      if (previousTurn) finalizeTurn(previousTurn);
      else clearTimers();
      setCompanionId(id);
      setPartialTranscript("");
      setStreamingText("");
      setActivePlan(undefined);
      setAgentSteps([]);
      setCurrentAgentRunId(undefined);
      setCurrentAgentConfirmationStepId(undefined);
      const initialMessages = (() => {
        try {
          const storedMessages = conversationId
            ? loadConversationMessages(conversationId)
            : (() => {
                const stored = localStorage.getItem(`hinaa-messages-${id}`);
                return stored ? restoreMessages(JSON.parse(stored)) : null;
              })();
          const restored = restoreMessages(storedMessages);
          if (restored && restored.length > 0) return restored;
        } catch {}
        return [createMessage("assistant", companionProfiles[id].greeting)];
      })();
      setMessages(initialMessages);
      setState("idle");
    },
    [clearTimers, companionId, conversationId, finalizeTurn],
  );

  const resetConversation = useCallback((newId?: string) => {
    const previousTurn = activeTurnId.current;
    currentAbort.current?.abort();
    if (previousTurn) finalizeTurn(previousTurn);
    else clearTimers();
    setPartialTranscript("");
    setStreamingText("");
    setActivePlan(undefined);
    setAgentSteps([]);
    setIsSearching(false);
    setSearchQuery("");
    setCurrentAgentRunId(undefined);
    setCurrentAgentConfirmationStepId(undefined);
    setMessages([createMessage("assistant", companionProfiles[companionId].greeting)]);
    setState("idle");
  }, [clearTimers, companionId, finalizeTurn]);

  const stop = useCallback(() => {
    const previousTurn = activeTurnId.current;
    currentAbort.current?.abort();
    if (currentAgentRunId) {
      void fetch(`/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/cancel`, {
        method: "POST",
      }).catch(() => undefined);
      setAgentSteps((current) =>
        current.map((step) => ({ ...step, status: step.status === "done" ? step.status : "cancelled" })),
      );
    }
    if (previousTurn) {
      finalizeTurn(previousTurn);
      return;
    }
    clearTimers();
    setPartialTranscript("");
    setStreamingText("");
    setState("idle");
  }, [clearTimers, currentAgentRunId, finalizeTurn]);

  const cancelCurrentAgentRun = useCallback(async () => {
    if (!currentAgentRunId) return;
    await fetch(`/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/cancel`, {
      method: "POST",
    }).catch(() => undefined);
    setAgentSteps((current) =>
      current.map((step) => ({ ...step, status: step.status === "done" ? step.status : "cancelled" })),
    );
    setState("idle");
  }, [currentAgentRunId]);

  const resumeCurrentAgentRun = useCallback(async () => {
    if (!currentAgentRunId) return;
    const response = await fetch(`/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/resume`, {
      method: "POST",
    });
    if (!response.ok) throw new Error(`Resume failed (${response.status})`);
    setAgentSteps((current) =>
      current.map((step) =>
        step.status === "pending" || step.status === "cancelled"
          ? { ...step, status: "active", detail: "Runtime resume requested" }
          : step,
      ),
    );
    setState("thinking");
  }, [currentAgentRunId]);

  const confirmCurrentAgentStep = useCallback(async (approved: boolean) => {
    if (!currentAgentRunId || !currentAgentConfirmationStepId) return;
    const response = await fetch(`/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stepId: currentAgentConfirmationStepId, approved }),
    });
    if (!response.ok) throw new Error(`Confirmation failed (${response.status})`);
    setAgentSteps((current) =>
      current.map((step) =>
        step.id === currentAgentConfirmationStepId
          ? {
              ...step,
              status: approved ? "active" : "cancelled",
              detail: approved ? "Approval sent to runtime" : "Rejected by user",
            }
          : step,
      ),
    );
    if (!approved) setState("idle");
  }, [currentAgentConfirmationStepId, currentAgentRunId]);

  const recoverCurrentAgentRun = useCallback(async () => {
    if (!currentAgentRunId) return;
    const response = await fetch(`/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/recover`, {
      method: "POST",
    });
    if (!response.ok) throw new Error(`Recovery failed (${response.status})`);
    setAgentSteps((current) => [
      ...current.filter((step) => step.id !== "run-recovery"),
      {
        id: "run-recovery",
        label: "Recovery requested",
        status: "active",
        detail: "Runtime is restoring safe resumable work",
      },
    ]);
    setState("thinking");
  }, [currentAgentRunId]);

  const sendText = useCallback(
    async (
      rawText: string,
      options?: {
        forceBackend?: boolean;
        responseMode?: ResponseMode;
        imageUrl?: string;
        attachment_ids?: string[];
        attachments?: import("./types").MessageAttachment[];
        imageEngine?: string;
        voiceEngine?: string;
      },
    ) => {
      const text = rawText.trim();
      if (!text) return;

      const previousTurn = activeTurnId.current;
      currentAbort.current?.abort();
      if (previousTurn) finalizeTurn(previousTurn);
      else clearTimers();
      const turnId = `turn-${++turnSequence.current}`;
      activeTurnId.current = turnId;
      const abortController = new AbortController();
      currentAbort.current = abortController;
      setMessages((current) => [
        ...current,
        createMessage("user", text, {
          imageUrl: options?.imageUrl,
          attachments: options?.attachments,
        }),
      ]);
      setPartialTranscript("");
      setStreamingText("");
      setActivePlan(undefined);
      setAgentSteps([]);
      setCurrentAgentRunId(undefined);
      setCurrentAgentConfirmationStepId(undefined);
      setState("thinking");

      let streamRafId: any = null;
      try {
        let rawStreamed = "";
        let streamed = "";
        let completedPlan: AssistantTurnPlan | undefined;
        let providerLatencyMs: number | undefined;
        const language = resolveTurnLanguage(text, languagePolicy);
        // Snapshot routing for this turn so it can't change mid-stream
        const isMockAllowed = !import.meta.env.PROD || import.meta.env.VITE_ALLOW_MOCK === "true";
        let turnMode = routing.activeMode ?? (import.meta.env.PROD ? "claude" : "mock");
        if (!isMockAllowed && turnMode === "mock") {
          turnMode = "claude";
        }
        const turnModel = routing.activeModel ?? "";
        
        const selectedProvider =
          turnMode !== "mock" || options?.forceBackend || !isMockAllowed
            ? new BackendConversationProvider(turnMode === "mock" ? "claude" : turnMode)
            : provider.current;
            
        for await (const event of selectedProvider.streamTurn({
          text,
          companionId,
          signal: abortController.signal,
          language,
          responseMode: options?.responseMode,
          brainModel: turnModel,
          imageEngine: options?.imageEngine,
          voiceEngine: options?.voiceEngine,
          conversationId: conversationId || undefined,
          imageUrl: options?.imageUrl,
          attachment_ids: options?.attachment_ids,
          attachments: options?.attachments,
        })) {
          if (activeTurnId.current !== turnId || abortController.signal.aborted) return undefined;
          if (event.type === "thinking") {
            setState("thinking");
          } else if (event.type === "search.started") {
            setIsSearching(true);
            setSearchQuery(event.query);
          } else if (event.type === "search.completed") {
            setIsSearching(false);
          } else if (event.type === "text.delta") {
            setIsSearching(false);
            rawStreamed += event.delta;
            // Batch streaming deltas via requestAnimationFrame to avoid React thrashing during 50K/100K streams
            if (!streamRafId) {
              const scheduleFrame =
                typeof window !== "undefined" && typeof window.requestAnimationFrame === "function"
                  ? window.requestAnimationFrame
                  : (cb: () => void) => setTimeout(cb, 16);
              streamRafId = scheduleFrame(() => {
                streamRafId = null;
                streamed = getSafeAssistantStreamingText(rawStreamed);
                setStreamingText(streamed);
                setState(streamed ? "speaking" : "thinking");
              });
            }
          } else if (event.type === "plan") {
            if (streamRafId) {
              const cancelFrame =
                typeof window !== "undefined" && typeof window.cancelAnimationFrame === "function"
                  ? window.cancelAnimationFrame
                  : clearTimeout;
              cancelFrame(streamRafId);
              streamRafId = null;
            }
            setIsSearching(false);
            setSearchQuery("");
            setStreamingText("");
            completedPlan = event.plan;
            setActivePlan(event.plan);
            setMessages((current) => [
              ...current,
              createMessage("assistant", getAssistantDisplayText(serializeAssistantTurn(event.plan)), {
              content: serializeAssistantTurn(event.plan),
              plan: event.plan,
            }),
            ]);
            // Do not finalize here. Providers can legitimately emit trailing
            // usage metadata after the plan; finalizing early makes the next
            // stream event look stale and drops the completed turn before typed
            // chat can hand its spokenText to the playback owner.
          } else if (event.type === "agent.event") {
            setCurrentAgentRunId(event.event.run_id);
            if (event.event.event_type === "confirmation.required") {
              setCurrentAgentConfirmationStepId(event.event.step_id ?? undefined);
            }
            if (
              event.event.event_type === "agent.run.completed" ||
              event.event.event_type === "agent.run.failed" ||
              event.event.event_type === "agent.run.cancelled"
            ) {
              setCurrentAgentConfirmationStepId(undefined);
            }
            setAgentSteps((current) => runtimeEventToSteps(current, event.event));
          } else {
            providerLatencyMs = event.latencyMs;
          }
        }
        if (!completedPlan) {
          finalizeTurn(turnId, { errorText: "Hinaa did not receive a complete response. Please try again." });
          return undefined;
        }
        if (!finalizeTurn(turnId, { preservePartial: true })) return undefined;
        // The controller is now unlocked, while the immutable turnId remains
        // available to the playback owner. This makes typed-chat TTS traceable
        // without allowing stale stream callbacks to mutate a later turn.
        return { turnId, plan: completedPlan, providerLatencyMs };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          finalizeTurn(turnId);
          return undefined;
        }
        const message = error instanceof Error ? error.message : "";
        const isSchemaError =
          (error as any)?.name === "ZodError" ||
          message.includes("unrecognized_keys") ||
          message.includes("validation_error") ||
          message.includes("Invalid input");
        const isRateLimit =
          message.includes("PROVIDER_RATE_LIMIT") ||
          message.includes("429") ||
          message.includes("rate_limit_exceeded") ||
          message.includes("temporarily rate limited");
        const friendly = isSchemaError
          ? "HINAA encountered a plan formatting error while generating this response. Your prompt is preserved."
          : isRateLimit
          ? "The brain gateway is temporarily rate limited. Your prompt is preserved, and Hinaa will auto-route to an available brain."
          : message.includes("PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE") || message.includes("capacity")
            ? "The gateway is temporarily at capacity. Your prompt is preserved."
            : message.includes("PROVIDER_KEY_INVALID") || message.includes("PROVIDER_AUTH_FAILED")
            ? routing.activeMode === "claude"
              ? "Claude could not authenticate. Please verify your Claude gateway key and endpoint."
              : "The selected brain could not authenticate. Check its configuration and retry."
            : message.includes("PROVIDER_UNAVAILABLE") || message.includes("cooldown") || message.includes("timeout")
            ? "The primary brain is reconnecting. You can send your message again or switch to Gemini in brain settings."
            : `Execution paused safely. ${message} Try another brain model or text mode.`;
        finalizeTurn(turnId, { errorText: friendly });
        return undefined;
      } finally {
        if (streamRafId) {
          const cancelFrame =
            typeof window !== "undefined" && typeof window.cancelAnimationFrame === "function"
              ? window.cancelAnimationFrame
              : clearTimeout;
          cancelFrame(streamRafId);
          streamRafId = null;
        }
        if (currentAbort.current === abortController) currentAbort.current = undefined;
      }
    },
    [clearTimers, companionId, finalizeTurn, languagePolicy, routing],
  );

  const resolveToolRequest = useCallback(
    async (
      messageId: string,
      request: AssistantTurnPlan["toolRequests"][number],
      approved: boolean,
      approvalSource: "user" | "standing-consent" = "user",
    ) => {
      const actionId = request.toolName;
      const requestKey = `${messageId}:${actionId}:${JSON.stringify(request.parameters)}`;
      if (!approved) {
        setMessages((current) => current.map((message) => message.id === messageId ? {
          ...message,
          toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
            ...activity, status: "cancelled", label: `Declined: ${request.toolName}`,
          } : activity),
        } : message));
        return;
      }

      if (resolvingToolRequestIds.current.has(requestKey)) return;
      resolvingToolRequestIds.current.add(requestKey);
      setMessages((current) => current.map((message) => message.id === messageId ? {
        ...message,
        toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
          ...activity, status: "running", label: `Running approved action: ${request.toolName}`,
        } : activity),
      } : message));

      try {
        const response = await fetch("/api/v1/tools/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...request, confirmed: true, approvalSource }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.status === "error") {
          throw new Error(payload.detail || payload.error || `Action failed (${response.status})`);
        }
        if (payload.status === "processing" && payload.job_id) {
          setMessages((current) => current.map((message) => message.id === messageId ? {
            ...message,
            toolResults: [...(message.toolResults || []).filter((item) => item.toolName !== request.toolName), { toolName: request.toolName, result: payload }],
            toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
              ...activity, status: "running", label: `Working locally: ${request.toolName}`,
            } : activity),
          } : message));
          void (async () => {
            for (let attempt = 0; attempt < 180; attempt += 1) {
              await new Promise((resolve) => window.setTimeout(resolve, 1500));
              try {
                const pollResponse = await fetch(`/api/v1/tools/poll?job_id=${encodeURIComponent(payload.job_id)}`);
                const progress = await pollResponse.json();
                if (!pollResponse.ok) continue;
                setMessages((current) => current.map((message) => message.id === messageId ? {
                  ...message,
                  toolResults: [...(message.toolResults || []).filter((item) => item.toolName !== request.toolName), { toolName: request.toolName, result: progress }],
                  toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
                    ...activity,
                    status: progress.status === "success" ? "complete" : progress.status === "error" ? "error" : "running",
                    label: progress.status === "success" ? `Completed: ${request.toolName}` : progress.status === "error" ? `Failed: ${request.toolName}` : `Working locally: ${request.toolName}`,
                  } : activity),
                } : message));
                if (progress.status === "success" || progress.status === "error") return;
              } catch {
                // Keep the last known progress visible; the next poll may recover.
              }
            }
          })();
          return;
        }
        const outcome = resolveToolOutcome(request.toolName, payload);
        setMessages((current) => current.map((message) => message.id === messageId ? {
          ...message,
          toolResults: [...(message.toolResults || []).filter((item) => item.toolName !== request.toolName), { toolName: request.toolName, result: outcome.result }],
          toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
            ...activity, status: outcome.status, label: outcome.label,
          } : activity),
        } : message));
      } catch (error) {
        const label = error instanceof Error ? error.message : "Approved action failed";
        setMessages((current) => current.map((message) => message.id === messageId ? {
          ...message,
          toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
            ...activity, status: "error", label: `Failed: ${label}`,
          } : activity),
        } : message));
      } finally {
        resolvingToolRequestIds.current.delete(requestKey);
      }
    },
    [],
  );

  const startMockListening = useCallback(() => {
    clearTimers();
    currentAbort.current?.abort();
    setStreamingText("");
    setActivePlan(undefined);
    setState("listening");
    setPartialTranscript("Mock demo…");
    timers.current.push(
      window.setTimeout(
        () => setPartialTranscript("Mock microphone demo…"),
        320,
      ),
    );
    timers.current.push(
      window.setTimeout(() => {
        const finalText =
          "Mock microphone demo transcript. Real speech recognition is not active.";
        setPartialTranscript(finalText);
        void sendText(finalText);
      }, 820),
    );
  }, [clearTimers, sendText]);

  const beginListening = useCallback(() => {
    clearTimers();
    currentAbort.current?.abort();
    setPartialTranscript("");
    setStreamingText("");
    setActivePlan(undefined);
    setState("listening");
  }, [clearTimers]);

  const applyLivePartial = useCallback((text: string) => {
    setPartialTranscript(text);
    setState("listening");
  }, []);

  const applyLiveFinal = useCallback((text: string) => {
    setPartialTranscript("");
    setStreamingText("");
    setMessages((current) => [
      ...current,
      createMessage("user", text),
    ]);
    setState("thinking");
  }, []);

  const applyLiveDelta = useCallback((delta: string) => {
    setStreamingText((current) => current + delta);
    setState("speaking");
  }, []);

  const applyLivePlan = useCallback((plan: AssistantTurnPlan) => {
    setActivePlan(plan);
    setStreamingText("");
    setMessages((current) => [
      ...current,
      createMessage("assistant", getAssistantDisplayText(serializeAssistantTurn(plan)), {
        content: serializeAssistantTurn(plan),
        plan,
      }),
    ]);
    // Live audio may continue independently, but the text composer must never
    // remain blocked after the final plan is available.
    setState("idle");
  }, []);

  const applyLiveError = useCallback((message: string) => {
    clearTimers();
    setPartialTranscript("");
    setStreamingText("");
    setMessages((current) => [
      ...current,
      createMessage("assistant", `Live session ended safely. ${message}`),
    ]);
    setState("idle");
  }, [clearTimers]);

  useEffect(
    () => () => {
      clearTimers();
      currentAbort.current?.abort();
    },
    [clearTimers],
  );

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    const toolRequests =
      lastMessage?.role === "assistant" ? lastMessage.plan?.toolRequests : undefined;
    if (!lastMessage || !toolRequests?.length) return;
    if (processedToolMessageIds.current.has(lastMessage.id)) return;

    processedToolMessageIds.current.add(lastMessage.id);
    const messageId = lastMessage.id;

    // Autonomy mode carries standing consent from Settings, so a proposal is
    // executed immediately. With autonomy off, a model proposal is still not
    // consent to browse, send, purchase, or call an external service: the action
    // stays visible and pending until it is explicitly allowed or declined, and
    // only then is it submitted with `confirmed: true`.
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId
          ? {
              ...message,
              toolActivity: toolRequests.map((request) => ({
                id: request.toolName,
                status: "pending" as const,
                label: autoRunTools
                  ? `Auto-running: ${request.toolName}`
                  : `Proposed action: ${request.toolName}`,
              })),
            }
          : message,
      ),
    );

    if (!autoRunTools) return;
    for (const request of toolRequests) {
      void resolveToolRequest(messageId, request, true, "standing-consent");
    }
  }, [messages, autoRunTools, resolveToolRequest]);

  return {
    companionId,
    switchCompanion,
    resetConversation,
    state,
    messages,
    setMessages,
    partialTranscript,
    streamingText,
    routing,
    activePlan,
    agentSteps,
    isSearching,
    searchQuery,
    currentAgentRunId,
    currentAgentConfirmationStepId,
    cancelCurrentAgentRun,
    resumeCurrentAgentRun,
    confirmCurrentAgentStep,
    recoverCurrentAgentRun,
    sendText,
    startMockListening,
    beginListening,
    stop,
    applyLivePartial,
    applyLiveFinal,
    applyLiveDelta,
    applyLivePlan,
    applyLiveError,
    resolveToolRequest,
    setLiveState: setState,
  };
}
