import { useCallback, useEffect, useRef, useState } from "react";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
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
  sendText: (text: string) => Promise<void>;
  startMockListening: () => void;
  stop: () => void;
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
    async (rawText: string) => {
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
        for await (const event of provider.current.streamTurn({
          text,
          companionId,
          signal: abortController.signal,
        })) {
          if (event.type === "thinking") {
            setState("thinking");
          } else if (event.type === "text.delta") {
            streamed += event.delta;
            setStreamingText(streamed);
            setState("speaking");
          } else {
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
          }
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        setStreamingText("");
        setState("error");
        setMessages((current) => [
          ...current,
          {
            id: createId(),
            role: "assistant",
            text: "Mock response failed safely. Try again or continue with text mode.",
          },
        ]);
      } finally {
        if (currentAbort.current === abortController)
          currentAbort.current = undefined;
      }
    },
    [clearTimers, companionId],
  );

  const startMockListening = useCallback(() => {
    clearTimers();
    currentAbort.current?.abort();
    setStreamingText("");
    setActivePlan(undefined);
    setState("listening");
    setPartialTranscript("Aaja ko…");
    timers.current.push(
      window.setTimeout(() => setPartialTranscript("Aaja ko assignment…"), 320),
    );
    timers.current.push(
      window.setTimeout(() => {
        const finalText = "Aaja ko assignment malai explain gardeu na";
        setPartialTranscript(finalText);
        void sendText(finalText);
      }, 820),
    );
  }, [clearTimers, sendText]);

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
    sendText,
    startMockListening,
    stop,
  };
}
