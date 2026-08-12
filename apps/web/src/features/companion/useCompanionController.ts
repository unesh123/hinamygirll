import { useCallback, useEffect, useRef, useState } from "react";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import { BackendConversationProvider } from "../providers/backendConversationProvider";
import { MockConversationProvider } from "../providers/mockConversationProvider";
import {
  companionProfiles,
  type CompanionId,
  type CompanionState,
  type TranscriptMessage,
} from "./types";
import type { ProviderRuntimeSelection } from "../providers/utils/resolveProviderSelection";
import type { ActiveLanguagePolicy } from "../settings/types/settings";
import {
  deserializeAssistantTurn,
  getAssistantDisplayText,
  serializeAssistantTurn,
} from "./assistantTurnCodec";

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

export interface CompanionController {
  companionId: CompanionId;
  switchCompanion: (id: CompanionId) => void;
  resetConversation: () => void;
  state: CompanionState;
  messages: TranscriptMessage[];
  partialTranscript: string;
  streamingText: string;
  routing: ProviderRuntimeSelection;
  activePlan?: AssistantTurnPlan;
  sendText: (
    text: string,
    options?: { forceBackend?: boolean },
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
  routing: ProviderRuntimeSelection;
  languagePolicy: ActiveLanguagePolicy;
}

function resolveTurnLanguage(text: string, policy: ActiveLanguagePolicy): "en-US" | "hi-IN" {
  if (policy === "hi-IN") return "hi-IN";
  if (policy === "en-US") return "en-US";
  return /[\u0900-\u097F]/.test(text) ? "hi-IN" : "en-US";
}

export function useCompanionController({ routing, languagePolicy }: CompanionControllerOptions): CompanionController {
  const [companionId, setCompanionId] = useState<CompanionId>("hinaa");
  const [state, setState] = useState<CompanionState>("idle");
  const [messages, setMessages] = useState<TranscriptMessage[]>(() => {
    try {
      const stored = localStorage.getItem(`hinaa-messages-hinaa`);
      if (stored) {
        const restored = restoreMessages(JSON.parse(stored));
        if (restored) return restored;
      }
    } catch {}
    return [createMessage("assistant", companionProfiles.hinaa.greeting)];
  });

  useEffect(() => {
    localStorage.setItem(`hinaa-messages-${companionId}`, JSON.stringify(messages));
  }, [messages, companionId]);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [activePlan, setActivePlan] = useState<AssistantTurnPlan>();
  const provider = useRef(new MockConversationProvider());
  const currentAbort = useRef<AbortController | undefined>(undefined);
  const timers = useRef<number[]>([]);
  const processedToolMessageIds = useRef<Set<string>>(new Set());
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
      const initialMessages = (() => {
        try {
          const stored = localStorage.getItem(`hinaa-messages-${id}`);
          if (stored) {
            const restored = restoreMessages(JSON.parse(stored));
            if (restored) return restored;
          }
        } catch {}
        return [createMessage("assistant", companionProfiles[id].greeting)];
      })();
      setMessages(initialMessages);
      setState("idle");
    },
    [clearTimers, companionId, finalizeTurn],
  );

  const resetConversation = useCallback(() => {
    const previousTurn = activeTurnId.current;
    currentAbort.current?.abort();
    if (previousTurn) finalizeTurn(previousTurn);
    else clearTimers();
    setPartialTranscript("");
    setStreamingText("");
    setActivePlan(undefined);
    setMessages([createMessage("assistant", companionProfiles[companionId].greeting)]);
    setState("idle");
  }, [clearTimers, companionId, finalizeTurn]);

  const stop = useCallback(() => {
    const previousTurn = activeTurnId.current;
    currentAbort.current?.abort();
    if (previousTurn) {
      finalizeTurn(previousTurn);
      return;
    }
    clearTimers();
    setPartialTranscript("");
    setStreamingText("");
    setState("idle");
  }, [clearTimers, finalizeTurn]);

  const sendText = useCallback(
    async (rawText: string, options?: { forceBackend?: boolean }) => {
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
        createMessage("user", text),
      ]);
      setPartialTranscript("");
      setStreamingText("");
      setActivePlan(undefined);
      setState("thinking");

      try {
        let streamed = "";
        let completedPlan: AssistantTurnPlan | undefined;
        let providerLatencyMs: number | undefined;
        const language = resolveTurnLanguage(text, languagePolicy);
        // Snapshot routing for this turn so it can't change mid-stream
        const turnMode = routing.activeMode ?? "mock";
        const turnModel = routing.activeModel ?? "";
        
        const selectedProvider =
          turnMode !== "mock" || options?.forceBackend
            ? new BackendConversationProvider(turnMode)
            : provider.current;
            
        for await (const event of selectedProvider.streamTurn({
          text,
          companionId,
          signal: abortController.signal,
          language,
          brainModel: turnModel,
        })) {
          if (activeTurnId.current !== turnId || abortController.signal.aborted) return undefined;
          if (event.type === "thinking") {
            setState("thinking");
          } else if (event.type === "text.delta") {
            streamed += event.delta;
            setStreamingText(streamed);
            setState("speaking");
          } else if (event.type === "plan") {
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
        const friendly = message.includes("PROVIDER_RATE_LIMIT")
          ? "The selected brain key/model is rate limited. Switch the Brain model, wait a moment, or use the Codex key source."
          : `Response failed safely. ${message} Try another brain model or text mode.`;
        finalizeTurn(turnId, { errorText: friendly });
        return undefined;
      } finally {
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
    ) => {
      const actionId = request.toolName;
      if (!approved) {
        setMessages((current) => current.map((message) => message.id === messageId ? {
          ...message,
          toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
            ...activity, status: "cancelled", label: `Declined: ${request.toolName}`,
          } : activity),
        } : message));
        return;
      }

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
          body: JSON.stringify({ ...request, confirmed: true }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.status === "error") {
          throw new Error(payload.detail || payload.error || `Action failed (${response.status})`);
        }
        if (payload.status === "processing" && payload.job_id) {
          setMessages((current) => current.map((message) => message.id === messageId ? {
            ...message,
            toolResults: [...(message.toolResults || []), { toolName: request.toolName, result: payload }],
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
        setMessages((current) => current.map((message) => message.id === messageId ? {
          ...message,
          toolResults: [...(message.toolResults || []), { toolName: request.toolName, result: payload.data ?? payload }],
          toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
            ...activity, status: "complete", label: `Completed: ${request.toolName}`,
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
    // A model proposal is not consent to browse, send, purchase, or call an
    // external service. Keep it visible until a dedicated confirmation UI is
    // implemented, then submit with `confirmed: true` only after approval.
    setMessages((current) =>
      current.map((message) =>
        message.id === lastMessage.id
          ? {
              ...message,
              toolActivity: toolRequests.map((request) => ({
                id: request.toolName,
                status: "pending" as const,
                label: `Proposed action: ${request.toolName}`,
              })),
            }
          : message,
      ),
    );
  }, [messages]);

  return {
    companionId,
    switchCompanion,
    resetConversation,
    state,
    messages,
    partialTranscript,
    streamingText,
    routing,
    activePlan,
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
