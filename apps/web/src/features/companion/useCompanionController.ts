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

function createId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ?? `mock-${Date.now()}-${Math.random()}`
  );
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
    { plan: AssistantTurnPlan; providerLatencyMs?: number } | undefined
  >;
  startMockListening: () => void;
  beginListening: () => void;
  stop: () => void;
  applyLivePartial: (text: string) => void;
  applyLiveFinal: (text: string) => void;
  applyLiveDelta: (delta: string) => void;
  applyLivePlan: (plan: AssistantTurnPlan) => void;
  applyLiveError: (message: string) => void;
  setLiveState: (state: CompanionState) => void;
}

export interface CompanionControllerOptions {
  routing: ProviderRuntimeSelection;
}

export function useCompanionController({ routing }: CompanionControllerOptions): CompanionController {
  const [companionId, setCompanionId] = useState<CompanionId>("hinaa");
  const [state, setState] = useState<CompanionState>("idle");
  const [messages, setMessages] = useState<TranscriptMessage[]>(() => {
    try {
      const stored = localStorage.getItem(`hinaa-messages-hinaa`);
      if (stored) return JSON.parse(stored);
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

  const clearTimers = useCallback(() => {
    for (const timer of timers.current) window.clearTimeout(timer);
    timers.current = [];
  }, []);

  // Switching companion starts a fresh log with their own greeting, clears
  // any in-flight turn, and returns the stage to idle. Re-selecting the
  // already-active companion is a no-op — the transcript is left untouched.
  const switchCompanion = useCallback(
    (id: CompanionId) => {
      if (id === companionId) return;
      clearTimers();
      currentAbort.current?.abort();
      currentAbort.current = undefined;
      setCompanionId(id);
      setPartialTranscript("");
      setStreamingText("");
      setActivePlan(undefined);
      const initialMessages = (() => {
        try {
          const stored = localStorage.getItem(`hinaa-messages-${id}`);
          if (stored) return JSON.parse(stored);
        } catch {}
        return [createMessage("assistant", companionProfiles[id].greeting)];
      })();
      setMessages(initialMessages);
      setState("idle");
    },
    [clearTimers, companionId],
  );

  const resetConversation = useCallback(() => {
    clearTimers();
    currentAbort.current?.abort();
    currentAbort.current = undefined;
    setPartialTranscript("");
    setStreamingText("");
    setActivePlan(undefined);
    setMessages([createMessage("assistant", companionProfiles[companionId].greeting)]);
    setState("idle");
  }, [clearTimers, companionId]);

  const stop = useCallback(() => {
    clearTimers();
    currentAbort.current?.abort();
    currentAbort.current = undefined;
    setPartialTranscript("");
    setStreamingText("");
    setState("interrupted");
    timers.current.push(window.setTimeout(() => setState("idle"), 650));
  }, [clearTimers]);

  const sendText = useCallback(
    async (rawText: string, options?: { forceBackend?: boolean }) => {
      const text = rawText.trim();
      if (!text) return;

      clearTimers();
      currentAbort.current?.abort();
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
          brainModel: turnModel,
        })) {
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
              createMessage("assistant", event.plan.displayText, { plan: event.plan }),
            ]);
            setStreamingText("");
            setState("speaking");
            timers.current.push(window.setTimeout(() => setState("idle"), 950));
          } else {
            providerLatencyMs = event.latencyMs;
          }
        }
        return completedPlan
          ? { plan: completedPlan, providerLatencyMs }
          : undefined;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError")
          return undefined;
        const message = error instanceof Error ? error.message : "";
        const friendly = message.includes("PROVIDER_RATE_LIMIT")
          ? "The selected brain key/model is rate limited. Switch the Brain model, wait a moment, or use the Codex key source."
          : `Response failed safely. ${message} Try another brain model or text mode.`;
        setStreamingText("");
        setState("error");
        setMessages((current) => [
          ...current,
          createMessage("assistant", friendly),
        ]);
        timers.current.push(window.setTimeout(() => setState("idle"), 2500));
        return undefined;
      } finally {
        if (currentAbort.current === abortController)
          currentAbort.current = undefined;
      }
    },
    [clearTimers, companionId, routing],
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
      createMessage("assistant", plan.displayText, { plan }),
    ]);
    setState("speaking");
  }, []);

  const applyLiveError = useCallback((message: string) => {
    setPartialTranscript(message);
    setStreamingText("");
    setState("error");
    timers.current.push(window.setTimeout(() => setState("idle"), 2500));
  }, []);

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
    setLiveState: setState,
  };
}
