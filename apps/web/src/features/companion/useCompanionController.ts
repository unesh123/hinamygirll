import { useCallback, useEffect, useRef, useState } from "react";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { ProviderMode } from "../audio/api";
import { BackendConversationProvider } from "../providers/backendConversationProvider";
import { MockConversationProvider } from "../providers/mockConversationProvider";
import {
  companionProfiles,
  type CompanionId,
  type CompanionState,
  type TranscriptMessage,
} from "./types";

function createId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ?? `mock-${Date.now()}-${Math.random()}`
  );
}

export interface CompanionController {
  companionId: CompanionId;
  setCompanionId: (id: CompanionId) => void;
  state: CompanionState;
  messages: TranscriptMessage[];
  partialTranscript: string;
  streamingText: string;
  activePlan?: AssistantTurnPlan;
  providerMode: ProviderMode;
  setProviderMode: (mode: ProviderMode) => void;
  brainModel: string;
  setBrainModel: (model: string) => void;
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

export function useCompanionController(): CompanionController {
  const [companionId, setCompanionId] = useState<CompanionId>("hinaa");
  const [state, setState] = useState<CompanionState>("idle");
  const [messages, setMessages] = useState<TranscriptMessage[]>([
    {
      id: createId(),
      role: "assistant",
      text: companionProfiles.hinaa.greeting,
    },
  ]);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [activePlan, setActivePlan] = useState<AssistantTurnPlan>();
  const [providerMode, setProviderMode] = useState<ProviderMode>("mock");
  const [brainModel, setBrainModel] = useState("gpt-5-mini");
  const provider = useRef(new MockConversationProvider());
  const currentAbort = useRef<AbortController | undefined>(undefined);
  const timers = useRef<number[]>([]);

  const clearTimers = useCallback(() => {
    for (const timer of timers.current) window.clearTimeout(timer);
    timers.current = [];
  }, []);

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
        { id: createId(), role: "user", text },
      ]);
      setPartialTranscript("");
      setStreamingText("");
      setActivePlan(undefined);
      setState("thinking");

      try {
        let streamed = "";
        let completedPlan: AssistantTurnPlan | undefined;
        let providerLatencyMs: number | undefined;
        const selectedProvider =
          providerMode !== "mock" || options?.forceBackend
            ? new BackendConversationProvider(providerMode)
            : provider.current;
        for await (const event of selectedProvider.streamTurn({
          text,
          companionId,
          signal: abortController.signal,
          brainModel,
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
              {
                id: createId(),
                role: "assistant",
                text: event.plan.displayText,
                plan: event.plan,
              },
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
          {
            id: createId(),
            role: "assistant",
            text: friendly,
          },
        ]);
        return undefined;
      } finally {
        if (currentAbort.current === abortController)
          currentAbort.current = undefined;
      }
    },
    [brainModel, clearTimers, companionId, providerMode],
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
      { id: createId(), role: "user", text },
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
      { id: createId(), role: "assistant", text: plan.displayText, plan },
    ]);
    setState("speaking");
  }, []);

  const applyLiveError = useCallback((message: string) => {
    setPartialTranscript("");
    setStreamingText("");
    setState("error");
    setMessages((current) => [
      ...current,
      { id: createId(), role: "assistant", text: message },
    ]);
  }, []);

  useEffect(
    () => () => {
      clearTimers();
      currentAbort.current?.abort();
    },
    [clearTimers],
  );

  return {
    companionId,
    setCompanionId,
    state,
    messages,
    partialTranscript,
    streamingText,
    activePlan,
    providerMode,
    setProviderMode,
    brainModel,
    setBrainModel,
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
