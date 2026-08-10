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
  const [messages, setMessages] = useState<TranscriptMessage[]>([
    createMessage("assistant", companionProfiles.hinaa.greeting),
  ]);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [activePlan, setActivePlan] = useState<AssistantTurnPlan>();
  const provider = useRef(new MockConversationProvider());
  const currentAbort = useRef<AbortController | undefined>(undefined);
  const timers = useRef<number[]>([]);

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
      setMessages([createMessage("assistant", companionProfiles[id].greeting)]);
      setState("idle");
    },
    [clearTimers, companionId],
  );

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
  }, []);

  useEffect(
    () => () => {
      clearTimers();
      currentAbort.current?.abort();
    },
    [clearTimers],
  );

  const processedToolMessageIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (
      !lastMessage ||
      lastMessage.role !== "assistant" ||
      !lastMessage.plan?.toolRequests ||
      lastMessage.plan.toolRequests.length === 0
    ) {
      return;
    }

    if (processedToolMessageIds.current.has(lastMessage.id)) {
      return;
    }

    processedToolMessageIds.current.add(lastMessage.id);

    const runTools = async () => {
      // Mark as running
      setMessages((current) =>
        current.map((msg) =>
          msg.id === lastMessage.id
            ? {
                ...msg,
                toolActivity: lastMessage.plan!.toolRequests.map((req: any) => ({
                  id: req.toolName,
                  status: "running",
                  label: `Running ${req.toolName}...`,
                })),
                toolResults: [],
              }
            : msg
        )
      );

      for (const req of lastMessage.plan.toolRequests) {
        try {
          const res = await fetch("http://localhost:8000/v1/tools/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(req),
          });
          const data = await res.json();

          setMessages((current) =>
            current.map((msg) => {
              if (msg.id !== lastMessage.id) return msg;
              const results = msg.toolResults || [];
              const act = msg.toolActivity || [];
              return {
                ...msg,
                toolResults: [...results, { toolName: (req as any).toolName, result: data.data }],
                toolActivity: act.map((a) =>
                  a.id === (req as any).toolName
                    ? { ...a, status: "complete", label: `Completed ${(req as any).toolName}` }
                    : a
                ),
              };
            })
          );
        } catch (e) {
          console.error("Tool execution failed", e);
          setMessages((current) =>
            current.map((msg) => {
              if (msg.id !== lastMessage.id) return msg;
              const act = msg.toolActivity || [];
              return {
                ...msg,
                toolActivity: act.map((a) =>
                  a.id === (req as any).toolName
                    ? { ...a, status: "error", label: `Failed ${(req as any).toolName}` }
                    : a
                ),
              };
            })
          );
        }
      }
    };

    void runTools();
  }, [messages]);

  return {
    companionId,
    switchCompanion,
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
