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
import { HINAA_DEV_USER } from "../../lib/hinaaIdentity";
import { singleLine } from "../../lib/turnFailure";
import { recordMotionState } from "./motionLedger";

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

const META_REFLECTION_SPEECH_RE = /^\s*(?:the (?:instructions|system prompt|developer instructions|prompt) (?:are|say|states?|requires?|dictates?|strictly)|instructions (?:are|require|say|state)|turn \d+\+?(?:\s+only)?\s*:|turn \d+\+? means|unesh (?:just|is|has|asked|said|wants|did not|didn't)|(?:the )?user (?:just|is|has|asked|said|wants|did not|didn't)|i must (?:not )?(?:repeat|greet|answer|dive|respond|provide)|i should (?:not )?(?:force-feed|repeat|ask|give|respond)|my (?:persona|identity|character|task|goal) (?:is|requires)|acting as (?:hina|hinaa|companion)|character guidelines|(?:his|the) active topic is|(?:goal|plan|internal reasoning|reasoning|thinking|scratchpad)\s*:|analyzing (?:user|the prompt|request|context)|let (?:me|us) analyze|current turn\s*:)\b/im;

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

/** What a caller may attach to one turn. Declared once: the interface and the
 * implementation used to repeat this shape, and a field added to only one of
 * them passed the local typecheck and failed the production build. */
export interface SendTextOptions {
  forceBackend?: boolean;
  responseMode?: ResponseMode;
  imageUrl?: string;
  attachment_ids?: string[];
  /** Data URIs to feed as image-to-image references for this turn's drawing. */
  reference_images?: string[];
  attachments?: import("./types").MessageAttachment[];
  imageEngine?: string;
  voiceEngine?: string;
  onSentenceChunk?: (sentence: string, isFirst: boolean) => void;
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
    options?: SendTextOptions,
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
  // Mirror every companion state change into the backend run ledger. The
  // final `idle` after a reply is what makes the stop-fix auditable from the
  // server instead of only visible on screen.
  useEffect(() => {
    recordMotionState(state);
  }, [state]);
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
      const fallbackGreeting = [createMessage("assistant", companionProfiles[companionId]?.greeting ?? companionProfiles.hinaa.greeting)];
      setMessages(fallbackGreeting);
    }
  }, [conversationId, companionId]);

  useEffect(() => {
    const key = conversationId ? `hinaa-messages-${conversationId}` : `hinaa-messages-${companionId}`;
    if (conversationId) saveConversationMessages(conversationId, messages);
    else localStorage.setItem(key, JSON.stringify(messages));
  }, [messages, conversationId, companionId]);

  // Synchronize conversation messages from backend database for persistent continuity across reloads
  useEffect(() => {
    if (typeof conversationId !== "string" || !conversationId.trim()) return;
    const targetConvoId: string = conversationId.trim();
    let isCancelled = false;
    async function syncBackendMessages() {
      try {
        const res = await fetch(`/api/v1/conversations/${encodeURIComponent(targetConvoId)}/messages?limit=100`, {
          headers: { "X-HINAA-Dev-User": HINAA_DEV_USER },
        });
        if (!res.ok) return;
        const data = await res.json();
        const serverMessages: any[] = Array.isArray(data) ? data : data?.messages ?? [];
        if (serverMessages.length > 0 && !isCancelled) {
          const restored: TranscriptMessage[] = serverMessages.map((m) => {
            const rawContent = m.content || m.text || "";
            const plan = m.role === "assistant" && rawContent ? deserializeAssistantTurn(rawContent) : undefined;
            return {
              id: m.id || createId(),
              role: m.role || "assistant",
              text: plan ? getAssistantDisplayText(rawContent) : (m.text || m.content || ""),
              content: rawContent,
              plan,
              createdAt: m.createdAt || m.created_at || new Date().toISOString(),
              actionDraft: m.actionDraft || m.action_draft,
              attachments: m.attachments,
            };
          });
          if (restored.length > 0 && !isCancelled) {
            setMessages((current) => {
              if (current.length <= 1 || restored.length >= current.length) {
                saveConversationMessages(targetConvoId, restored);
                return restored;
              }
              return current;
            });
          }
        }
      } catch (err) {
        // Non-blocking background sync
      }
    }
    syncBackendMessages();
    return () => {
      isCancelled = true;
    };
  }, [conversationId]);
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
  const latestStreamedTextRef = useRef<string>("");

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

    // Commit any partially streamed text so user never loses generated content on pause or stop
    const partialToSave = latestStreamedTextRef.current.trim();
    if (partialToSave) {
      setMessages((current) => [...current, createMessage("assistant", partialToSave)]);
      latestStreamedTextRef.current = "";
    }

    setStreamingText("");
    setActivePlan(undefined);
    setCurrentAgentRunId(undefined);
    setCurrentAgentConfirmationStepId(undefined);
    setAgentSteps([]);
    const errorText = result.errorText;
    if (errorText && !partialToSave) {
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
    const initialGreeting = [createMessage("assistant", companionProfiles[companionId].greeting)];
    setMessages(initialGreeting);
    if (newId) {
      prevConvoIdRef.current = newId;
      saveConversationMessages(newId, initialGreeting);
    }
    processedToolMessageIds.current.clear();
    setState("idle");
  }, [clearTimers, companionId, finalizeTurn]);

  const stop = useCallback(() => {
    const previousTurn = activeTurnId.current;
    currentAbort.current?.abort();
    if (currentAgentRunId) {
      void fetch(`/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/cancel`, {
        method: "POST",
      }).catch(() => undefined);
    }
    setCurrentAgentRunId(undefined);
    setCurrentAgentConfirmationStepId(undefined);
    setAgentSteps([]);
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
    if (currentAgentRunId) {
      void fetch(`/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/cancel`, {
        method: "POST",
      }).catch(() => undefined);
    }
    setCurrentAgentRunId(undefined);
    setCurrentAgentConfirmationStepId(undefined);
    setAgentSteps([]);
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
      options?: SendTextOptions,
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
        let sentenceBuffer = "";
        let isFirstSentence = true;
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
          reference_images: options?.reference_images,
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
            sentenceBuffer += event.delta;
            latestStreamedTextRef.current = getSafeAssistantStreamingText(rawStreamed) || rawStreamed;
            
            // Check for sentence/clause boundary to stream speech concurrently with generation
            const sentenceMatch = sentenceBuffer.match(/^([\s\S]*?[.!?\n\u0964\u0965;])(?:\s+|$)/);
            const clauseMatch = (!sentenceMatch && sentenceBuffer.length > 45)
              ? sentenceBuffer.match(/^([\s\S]*?[,:\-–—])(?:\s+)/)
              : null;
            const match = sentenceMatch || clauseMatch;
            if (match) {
              const fullSentence = match[1].trim();
              sentenceBuffer = sentenceBuffer.slice(match[0].length);
              if (
                fullSentence.length > 2 &&
                !META_REFLECTION_SPEECH_RE.test(fullSentence) &&
                !/<(?:think|thought)>/i.test(fullSentence) &&
                options?.onSentenceChunk
              ) {
                try {
                  options.onSentenceChunk(fullSentence, isFirstSentence);
                } catch {
                  // Non-blocking
                }
                isFirstSentence = false;
              }
            }

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
            latestStreamedTextRef.current = "";
            const finalRemaining = sentenceBuffer.trim();
            if (
              finalRemaining.length > 2 &&
              !META_REFLECTION_SPEECH_RE.test(finalRemaining) &&
              !/<(?:think|thought)>/i.test(finalRemaining) &&
              options?.onSentenceChunk
            ) {
              try {
                options.onSentenceChunk(finalRemaining, isFirstSentence);
              } catch {
                // Non-blocking
              }
              sentenceBuffer = "";
            }
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
              setCurrentAgentRunId(undefined);
            }
            setAgentSteps((current) => runtimeEventToSteps(current, event.event));
          } else if (event.type === "usage") {
            providerLatencyMs = event.latencyMs;
          } else if (event.type === "astra.tool") {
            if (event.status === "started" || event.status === "progress") {
              setState("using_tool");
            }
          } else if (event.type === "astra.route") {
            // Astra route telemetry received
          } else if (event.type === "astra.entity") {
            // Astra grounded entity resolution received
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
        const code =
          typeof (error as any)?.code === "string"
            ? String((error as any).code).toUpperCase()
            : "";
        const message = error instanceof Error ? singleLine(error.message) : "";
        const isSchemaError =
          (error as any)?.name === "ZodError" ||
          code === "VALIDATION_ERROR" ||
          message.includes("unrecognized_keys") ||
          message.includes("validation_error") ||
          message.includes("Invalid input");
        const isRateLimit =
          code === "PROVIDER_RATE_LIMIT" ||
          message.includes("429") ||
          message.includes("rate_limit_exceeded") ||
          message.includes("rate limited");
        const friendly = isSchemaError
          ? "HINAA encountered a plan formatting error while generating this response. Your prompt is preserved."
          : isRateLimit
          ? "The brain gateway is temporarily rate limited. Your prompt is preserved, and Hinaa will auto-route to an available brain."
          : code === "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE" || message.includes("capacity")
            ? "The gateway is temporarily at capacity. Your prompt is preserved."
            : code === "PROVIDER_KEY_INVALID" || code === "PROVIDER_AUTH_FAILED"
            ? routing.activeMode === "claude"
              ? "Claude could not authenticate. Please verify your Claude gateway key and endpoint."
              : "The selected brain could not authenticate. Check its configuration and retry."
            : code === "PROVIDER_UNAVAILABLE" || message.includes("cooldown") || message.includes("timeout")
            ? "The primary brain is reconnecting. You can send your message again or switch to Gemini in brain settings."
            : message || "HINAA could not finish this turn. Your prompt is preserved.";
        finalizeTurn(turnId, { errorText: singleLine(friendly, "HINAA could not finish this turn.") });
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
        // A 200 carrying status "error" is the tool refusing, not a transport
        // fault. resolveToolOutcome labels it and the result reaches toolResults,
        // where the card can say so out loud. Throwing here buried the refusal in
        // an activity row that only renders while the turn is still thinking.
        if (!response.ok) {
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
                // The route answers "processing" | "completed" | "failed".
                const phase = progress.status === "completed"
                  ? "complete" as const
                  : progress.status === "failed" ? "error" as const : "running" as const;
                const reason = typeof progress.error === "string" && progress.error.trim()
                  ? progress.error.trim()
                  : request.toolName;
                const isImageTool = request.toolName === "image_generate" || request.toolName === "magnific_image_generate" || request.toolName === "freepik_image_generate";
                const generatedImages: string[] = Array.isArray(progress.images)
                  ? progress.images
                  : progress.image
                    ? [progress.image]
                    : progress.resultUrl
                      ? [progress.resultUrl]
                      : [];
                const firstImg = generatedImages[0] || progress.resultUrl || progress.thumbnailUrl || "";

                setMessages((current) => current.map((message) => {
                  if (message.id !== messageId) return message;

                  let nextActionDraft = message.actionDraft;
                  if (nextActionDraft && isImageTool && nextActionDraft.intent === "image.job") {
                    const existingData = (nextActionDraft.fields as any)?.data || nextActionDraft.fields || {};
                    const updatedFieldsData = {
                      ...existingData,
                      prompt: progress.prompt || existingData.prompt || "",
                      stage: phase === "complete" ? ("saved" as const) : phase === "error" ? ("failed" as const) : ("generating" as const),
                      resultUrl: firstImg || existingData.resultUrl || "",
                      thumbnailUrl: firstImg || existingData.thumbnailUrl || "",
                      images: generatedImages.length > 0 ? generatedImages : existingData.images,
                      slots: progress.slots || existingData.slots,
                      model: progress.mode ? (progress.mode.includes("flux") ? "FLUX.1 [dev]" : progress.mode) : (existingData.model || "FLUX.1 [dev]"),
                      resolution: progress.slots?.[0] ? `${progress.slots[0].width} × ${progress.slots[0].height}` : (existingData.resolution || "1024 × 1024"),
                    };
                    nextActionDraft = {
                      ...nextActionDraft,
                      status: phase === "complete" ? ("success" as const) : phase === "error" ? ("error" as const) : ("running" as const),
                      fields: (nextActionDraft.fields as any)?.data ? { ...nextActionDraft.fields, data: updatedFieldsData } : updatedFieldsData,
                    };
                  }

                  return {
                    ...message,
                    actionDraft: nextActionDraft,
                    toolResults: [...(message.toolResults || []).filter((item) => item.toolName !== request.toolName), { toolName: request.toolName, result: progress }],
                    toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
                      ...activity,
                      status: phase,
                      label: phase === "complete" ? `Completed: ${request.toolName}` : phase === "error" ? `Failed: ${reason}` : `Working locally: ${request.toolName}`,
                    } : activity),
                  };
                }));
                if (phase !== "running") return;
              } catch {
                // Keep the last known progress visible; the next poll may recover.
              }
            }
          })();
          return;
        }
        const outcome = resolveToolOutcome(request.toolName, payload);
        const isImageTool = request.toolName === "image_generate" || request.toolName === "magnific_image_generate" || request.toolName === "freepik_image_generate";
        const directImages: string[] = Array.isArray(payload.images)
          ? payload.images
          : payload.image
            ? [payload.image]
            : payload.resultUrl
              ? [payload.resultUrl]
              : [];
        const firstDirectImg = directImages[0] || payload.resultUrl || payload.thumbnailUrl || "";

        setMessages((current) => current.map((message) => {
          if (message.id !== messageId) return message;
          let nextActionDraft = message.actionDraft;
          if (nextActionDraft && isImageTool && nextActionDraft.intent === "image.job") {
            const existingData = (nextActionDraft.fields as any)?.data || nextActionDraft.fields || {};
            const isFinished = outcome.status === "complete" || Boolean(firstDirectImg);
            const updatedFieldsData = {
              ...existingData,
              prompt: payload.prompt || existingData.prompt || "",
              stage: isFinished ? ("saved" as const) : outcome.status === "error" ? ("failed" as const) : ("generating" as const),
              resultUrl: firstDirectImg || existingData.resultUrl || "",
              thumbnailUrl: firstDirectImg || existingData.thumbnailUrl || "",
              images: directImages.length > 0 ? directImages : existingData.images,
              slots: payload.slots || existingData.slots,
              model: payload.mode ? (payload.mode.includes("flux") ? "FLUX.1 [dev]" : payload.mode) : (existingData.model || "FLUX.1 [dev]"),
              resolution: payload.slots?.[0] ? `${payload.slots[0].width} × ${payload.slots[0].height}` : (existingData.resolution || "1024 × 1024"),
            };
            nextActionDraft = {
              ...nextActionDraft,
              status: isFinished ? ("success" as const) : outcome.status === "error" ? ("error" as const) : ("running" as const),
              fields: (nextActionDraft.fields as any)?.data ? { ...nextActionDraft.fields, data: updatedFieldsData } : updatedFieldsData,
            };
          }

          return {
            ...message,
            actionDraft: nextActionDraft,
            toolResults: [...(message.toolResults || []).filter((item) => item.toolName !== request.toolName), { toolName: request.toolName, result: outcome.result }],
            toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
              ...activity, status: outcome.status, label: outcome.label,
            } : activity),
          };
        }));
      } catch (error) {
        const label = error instanceof Error ? error.message : "Approved action failed";
        setMessages((current) => current.map((message) => {
          if (message.id !== messageId) return message;
          let nextActionDraft = message.actionDraft;
          if (nextActionDraft && nextActionDraft.intent === "image.job") {
            const existingData = (nextActionDraft.fields as any)?.data || nextActionDraft.fields || {};
            const updatedFieldsData = {
              ...existingData,
              stage: "failed" as const,
              note: label,
            };
            nextActionDraft = {
              ...nextActionDraft,
              status: "error" as const,
              fields: (nextActionDraft.fields as any)?.data ? { ...nextActionDraft.fields, data: updatedFieldsData } : updatedFieldsData,
            };
          }
          return {
            ...message,
            actionDraft: nextActionDraft,
            toolResults: [...(message.toolResults || []).filter((item) => item.toolName !== request.toolName), { toolName: request.toolName, result: { status: "error", error: label } }],
            toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
              ...activity, status: "error", label: `Failed: ${label}`,
            } : activity),
          };
        }));
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
    const rawToolRequests =
      lastMessage?.role === "assistant" ? lastMessage.plan?.toolRequests : undefined;
    if (!lastMessage || !rawToolRequests?.length) return;
    if (processedToolMessageIds.current.has(lastMessage.id)) return;

    // Filter out informational search tools: they belong to the pre-generation retrieval
    // phase and must never be shown as pending actions or auto-run after an answer is generated.
    const SEARCH_TOOL_NAMES = new Set([
      "web_search",
      "web_research",
      "web_answer",
      "web_extract",
      "finance_research",
      "deep_research",
      "image_search",
    ]);
    const toolRequests = rawToolRequests.filter((r) => !SEARCH_TOOL_NAMES.has(r.toolName));
    if (!toolRequests.length) {
      processedToolMessageIds.current.add(lastMessage.id);
      return;
    }

    // Never re-execute tools that were already resolved (e.g. restored from persistent storage)
    const allAlreadyDone = toolRequests.every(
      (r) =>
        lastMessage.toolResults?.some((tr) => tr.toolName === r.toolName) ||
        lastMessage.toolActivity?.some((ta) => ta.id === r.toolName && (ta.status === "complete" || ta.status === "error")) ||
        lastMessage.actionDraft?.status === "success" ||
        lastMessage.actionDraft?.fields?.data?.stage === "saved",
    );
    if (allAlreadyDone) {
      processedToolMessageIds.current.add(lastMessage.id);
      return;
    }

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
                status: autoRunTools ? ("running" as const) : ("pending" as const),
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
