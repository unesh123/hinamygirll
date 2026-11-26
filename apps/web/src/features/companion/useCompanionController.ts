import { StreamingSpeechText } from "../audio/streamingSpeechText";
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
import { resolveConversationLocale } from "../audio/languagePolicy";
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
import { HINAA_DEV_USER, hinaaIdentityHeaders } from "../../lib/hinaaIdentity";
import { singleLine } from "../../lib/turnFailure";
import { recordMotionState } from "./motionLedger";
import { hinaaUIController } from "../ui-control/HinaaUIController";

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
  const upsert = (step: LiveAgentStep, list: LiveAgentStep[] = previous) => {
    const existing = list.findIndex((item) => item.id === step.id);
    if (existing === -1) return [...list, step];
    const next = [...list];
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
  if (event.event_type === "agentic.started") {
    return upsert({
      id: "run",
      label: "Autonomous Loop Started",
      status: "active",
      detail: typeof payload.goal === "string" ? payload.goal : "Executing bounded multi-step plan",
    });
  }
  if (event.event_type === "agent.step.started") {
    const stepNum = typeof payload.step === "number" ? payload.step : undefined;
    const stepLabel = stepNum ? `Reasoning · Step ${stepNum}` : title;
    const settled = previous.map((s) =>
      s.status === "active" && (s.id === "run" || s.id === "plan" || s.id.startsWith("step-")) && s.id !== stepId
        ? { ...s, status: "done" as const }
        : s,
    );
    return upsert({ id: stepId, label: stepLabel, status: "active", detail: "Inspecting workspace & selecting next tool" }, settled);
  }
  if (event.event_type === "tool.started") {
    const tName = typeof payload.toolName === "string" ? payload.toolName : "tool";
    return upsert({ id: `tool-${stepId}-${tName}`, label: `Running ${tName}`, status: "active", detail: "Executing inside server runtime" });
  }
  if (event.event_type === "tool.completed") {
    const tName = typeof payload.toolName === "string" ? payload.toolName : "tool";
    const ms = typeof payload.durationMs === "number" ? `${Math.round(payload.durationMs)} ms` : "completed";
    return upsert({ id: `tool-${stepId}-${tName}`, label: `Completed ${tName}`, status: "done", detail: ms });
  }
  if (event.event_type === "tool.failed") {
    const tName = typeof payload.toolName === "string" ? payload.toolName : "tool";
    return upsert({ id: `tool-${stepId}-${tName}`, label: `Failed ${tName}`, status: "error", detail: typeof payload.error === "string" ? payload.error : "Tool returned an error" });
  }
  if (event.event_type === "artifact.ready") {
    const art = (payload.artifact && typeof payload.artifact === "object" ? payload.artifact : {}) as Record<string, unknown>;
    const artLabel = typeof art.filePath === "string" ? art.filePath : typeof art.filename === "string" ? art.filename : "Artifact ready";
    return upsert({ id: `art-${artLabel}`, label: `Produced ${artLabel}`, status: "done", detail: String(art.kind || "artifact") });
  }
  if (event.event_type === "agentic.completed") {
    return previous.map((step) => ({ ...step, status: step.status === "error" ? step.status : "done" }));
  }
  if (event.event_type === "agent.step.progress") {
    return upsert({ id: stepId, label: title, status: "active", detail: message ?? "Runtime step updated" });
  }
  if (event.event_type === "agent.step.completed") {
    const stepNum = typeof payload.step === "number" ? payload.step : undefined;
    if (stepNum) {
      return previous.map((s) =>
        s.id === stepId && s.status === "active"
          ? { ...s, status: "done" as const }
          : s,
      );
    }
    return upsert({ id: stepId, label: title, status: "done", detail: "Runtime step completed" });
  }
  if (event.event_type === "agent.step.failed") {
    return upsert({ id: stepId, label: title, status: "error", detail: message ?? "Runtime step failed" });
  }
  if (event.event_type === "confirmation.required") {
    const tName = typeof payload.tool === "string" ? payload.tool : title;
    const reason = typeof payload.reason === "string" ? payload.reason : "Waiting for your approval";
    return upsert({ id: stepId, label: `Approve ${tName}?`, status: "pending", detail: reason });
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
  persona_mode?: string;
  agenticMode?: boolean;
  /**
   * Resend from this transcript prefix (regenerate / edit): it replaces the visible
   * conversation and is the turn's entire context, even when empty.
   */
  historyBase?: TranscriptMessage[];
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
  currentAgentApprovalInfo: AgentApprovalInfo | null;
  approvalPending: boolean;
  approvalError: string | null;
  backgroundBuild: BackgroundBuildState | null;
  cancelBackgroundBuild: () => Promise<void>;
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

export interface BackgroundBuildState {
  runId: string;
  goal: string;
  status: "running" | "awaiting_approval" | "completed" | "failed" | "cancelled";
  phase?: string;
  headline?: string;
  elapsedMs?: number;
  step?: number;
  previewUrls?: string[];
  summary?: string;
  artifacts?: string[];
  filesChanged?: string[];
}

export interface AgentApprovalInfo {
  stepId: string;
  runId?: string;
  actionName: string;
  command?: string;
  detail?: string;
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

// Auto policies must not guess Hindi for all Devanagari (Nepali is Devanagari too) or English for all
// Latin text (Romanized Nepali/Hindi): unknowns stay "mixed" so she mirrors his language.
function resolveTurnLanguage(text: string, policy: ActiveLanguagePolicy) {
  return resolveConversationLocale(text, policy);
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
  const [currentAgentApprovalInfo, setCurrentAgentApprovalInfo] = useState<AgentApprovalInfo | null>(null);
  const [approvalPending, setApprovalPending] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [backgroundBuild, setBackgroundBuild] = useState<BackgroundBuildState | null>(null);
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
  // sendText is memoized without `messages`, so it reads the live transcript from here;
  // a captured `messages` would send a stale history after any re-memoization.
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

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
  const pendingAgenticApprovalRef = useRef<{
    runId: string;
    argumentsHash: string;
    tool?: string;
    command?: string;
    detail?: string;
  } | null>(null);
  const backgroundBuildRef = useRef<BackgroundBuildState | null>(null);
  backgroundBuildRef.current = backgroundBuild;
  const bgAbortRef = useRef<AbortController | null>(null);
  const bgFinalizedRunIdsRef = useRef<Set<string>>(new Set());
  const bgMilestonesRef = useRef<Map<string, string[]>>(new Map());

  useEffect(() => {
    return () => {
      bgAbortRef.current?.abort();
    };
  }, []);
  const turnSequence = useRef(0);
  const activeTurnId = useRef<string | null>(null);
  const finalizedTurnIds = useRef<Set<string>>(new Set());
  const latestStreamedTextRef = useRef<string>("");
  const liveDeltaBufferRef = useRef<string>("");
  const liveRafIdRef = useRef<number | null>(null);

  const clearTimers = useCallback(() => {
    for (const timer of timers.current) window.clearTimeout(timer);
    timers.current = [];
  }, []);

  type TurnFinalization = { errorText?: string; preservePartial?: boolean; planCompleted?: boolean };

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

    // Commit any partially streamed text so user never loses generated content on pause or stop,
    // but only if the turn did not already complete cleanly with a structured plan message.
    const partialToSave = latestStreamedTextRef.current.trim();
    if (partialToSave && !result.planCompleted) {
      setMessages((current) => [...current, createMessage("assistant", partialToSave)]);
    }
    latestStreamedTextRef.current = "";

    setStreamingText("");
    setActivePlan(undefined);
    const hasActiveBg =
      backgroundBuildRef.current?.status === "running" ||
      backgroundBuildRef.current?.status === "awaiting_approval";
    if (!pendingAgenticApprovalRef.current && !hasActiveBg) {
      setCurrentAgentRunId(undefined);
      setCurrentAgentConfirmationStepId(undefined);
      setCurrentAgentApprovalInfo(null);
      setAgentSteps([]);
    }
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
      bgAbortRef.current?.abort();
      bgAbortRef.current = null;
      pendingAgenticApprovalRef.current = null;
      setCurrentAgentApprovalInfo(null);
      setApprovalPending(false);
      setApprovalError(null);
      setBackgroundBuild(null);
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
    bgAbortRef.current?.abort();
    bgAbortRef.current = null;
    pendingAgenticApprovalRef.current = null;
    setCurrentAgentApprovalInfo(null);
    setApprovalPending(false);
    setApprovalError(null);
    setBackgroundBuild(null);
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
    pendingAgenticApprovalRef.current = null;
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
      const targetEndpoint =
        pendingAgenticApprovalRef.current?.runId === currentAgentRunId
          ? `/api/v1/agent/agentic-runs/${encodeURIComponent(currentAgentRunId)}/cancel`
          : `/api/v1/agent/runs/${encodeURIComponent(currentAgentRunId)}/cancel`;
      void fetch(targetEndpoint, {
        method: "POST",
      }).catch(() => undefined);
    }
    pendingAgenticApprovalRef.current = null;
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

  const subscribeBackgroundAgenticRun = useCallback((runId: string, goalHint?: string) => {
    if (!runId) return;
    bgAbortRef.current?.abort();
    const ac = new AbortController();
    bgAbortRef.current = ac;
    setCurrentAgentRunId(runId);
    setBackgroundBuild((prev) => ({
      runId,
      goal: goalHint || prev?.goal || "Autonomous background build",
      status: "running",
    }));

    void (async () => {
      try {
        const res = await fetch(`/api/v1/agent/agentic-runs/${encodeURIComponent(runId)}/stream`, {
          method: "GET",
          headers: { ...hinaaIdentityHeaders() },
          signal: ac.signal,
        });
        if (!res.ok || !res.body) {
          throw new Error(`Background stream failed (${res.status})`);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let bgSeq = 0;

        const handleFrame = (frame: Record<string, any>) => {
          const evtType = String(frame.type ?? frame.event_type ?? "");
          if (!evtType) return;

          if (evtType === "confirmation.required") {
            const stepKey = String(frame.step_id ?? frame.approval_id ?? "approval");
            const argHash = String(frame.arguments_hash ?? frame.argumentsHash ?? "");
            const toolName = typeof frame.tool === "string" ? frame.tool : "tool";
            const rawArgs = (frame.arguments && typeof frame.arguments === "object" ? frame.arguments : {}) as Record<string, unknown>;
            const command =
              typeof frame.command === "string"
                ? frame.command
                : typeof rawArgs.command === "string"
                  ? rawArgs.command
                  : typeof rawArgs.file_path === "string"
                    ? `${toolName} ${rawArgs.file_path}`
                    : undefined;
            const detail = String(frame.reason ?? frame.summary ?? "Awaiting explicit approval");
            if (argHash) {
              pendingAgenticApprovalRef.current = {
                runId,
                argumentsHash: argHash,
                tool: toolName,
                command,
                detail,
              };
            }
            setCurrentAgentRunId(runId);
            setCurrentAgentConfirmationStepId(stepKey);
            setCurrentAgentApprovalInfo({ stepId: stepKey, runId, actionName: toolName, command, detail });
            setApprovalError(null);
            setBackgroundBuild((prev) =>
              prev ? { ...prev, status: "awaiting_approval" } : { runId, goal: goalHint || "", status: "awaiting_approval" },
            );
            setAgentSteps((current) =>
              runtimeEventToSteps(current, {
                run_id: runId,
                step_id: stepKey,
                event_type: "confirmation.required",
                payload: frame,
                sequence: Number(frame.sequence ?? ++bgSeq),
                timestamp: String(frame.timestamp ?? new Date().toISOString()),
              }),
            );
            return;
          }

          if (evtType === "agent.progress_update") {
            const phase = String(frame.phase ?? "building");
            const headline = String(frame.headline ?? frame.summary ?? "Working in workspace...");
            const filesChanged = Array.isArray(frame.filesChanged)
              ? frame.filesChanged.map(String)
              : undefined;
            const previewUrls = Array.isArray(frame.previewUrls)
              ? frame.previewUrls.map(String)
              : undefined;
            const elapsedMs = typeof frame.elapsedMs === "number" ? frame.elapsedMs : undefined;
            const stepNum = typeof frame.step === "number" ? frame.step : undefined;

            setBackgroundBuild((prev) => ({
              runId,
              goal: prev?.goal || goalHint || "",
              status: phase === "awaiting_approval" ? "awaiting_approval" : (prev?.status ?? "running"),
              phase,
              headline,
              elapsedMs: elapsedMs ?? prev?.elapsedMs,
              step: stepNum ?? prev?.step,
              filesChanged: filesChanged ?? prev?.filesChanged,
              previewUrls: previewUrls ?? prev?.previewUrls,
              summary: prev?.summary,
              artifacts: prev?.artifacts,
            }));

            const prevList = bgMilestonesRef.current.get(runId) ?? [];
            const entry = `- **${phase.toUpperCase()}**: ${headline}`;
            const nextList = prevList[prevList.length - 1] === entry ? prevList : [...prevList, entry].slice(-6);
            bgMilestonesRef.current.set(runId, nextList);

            const liveCardId = `bg-live-${runId}`;
            const filesLine =
              filesChanged && filesChanged.length > 0
                ? `\n\n**Files Changed (${filesChanged.length}):** ${filesChanged.slice(-6).map((f) => `\`${f}\``).join(", ")}`
                : "";
            const previewLine =
              previewUrls && previewUrls.length > 0
                ? `\n\n**Live Preview:** ${previewUrls.map((u) => `[${u}](${u})`).join(" · ")}`
                : "";
            const cardText = `### Workspace Builder · ${phase.toUpperCase()}\n${nextList.join("\n")}${filesLine}${previewLine}`;
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === liveCardId);
              if (idx >= 0) {
                const copy = [...current];
                copy[idx] = { ...copy[idx], text: cardText };
                return copy;
              }
              return [...current, { ...createMessage("assistant", cardText), id: liveCardId }];
            });
            if (
              typeof window !== "undefined" &&
              (phase === "preview" || phase === "awaiting_approval" || phase === "completed")
            ) {
              window.dispatchEvent(
                new CustomEvent("hinaa:build-milestone", {
                  detail: { runId, phase, headline, previewUrls },
                }),
              );
            }
            return;
          }

          if (evtType === "agentic.finalized") {
            pendingAgenticApprovalRef.current = null;
            setCurrentAgentConfirmationStepId(undefined);
            setCurrentAgentApprovalInfo(null);
            setApprovalError(null);
            const finalStatus = String(frame.status || "completed");
            const mappedStatus: BackgroundBuildState["status"] =
              finalStatus === "cancelled"
                ? "cancelled"
                : finalStatus === "failed" || finalStatus === "blocked" || finalStatus === "budget_exhausted"
                  ? "failed"
                  : "completed";
            const filesChanged = Array.isArray(frame.filesChanged)
              ? frame.filesChanged.map(String)
              : Array.isArray(frame.files_changed)
                ? frame.files_changed.map(String)
                : undefined;
            const previewUrls = Array.isArray(frame.previewUrls)
              ? frame.previewUrls.map(String)
              : undefined;
            const artifactLinks = Array.isArray(frame.artifacts)
              ? frame.artifacts
                  .map((a: any) => String(a?.download_url || a?.filePath || ""))
                  .filter(Boolean)
              : undefined;
            setBackgroundBuild((prev) => ({
              runId,
              goal: prev?.goal || goalHint || "",
              status: mappedStatus,
              phase: mappedStatus,
              headline: typeof frame.summary === "string" ? frame.summary.slice(0, 120) : prev?.headline,
              summary: typeof frame.summary === "string" ? frame.summary : undefined,
              filesChanged: filesChanged ?? prev?.filesChanged,
              previewUrls: previewUrls ?? prev?.previewUrls,
              artifacts: artifactLinks,
            }));
            setAgentSteps((current) =>
              current.map((s) => (s.status === "pending" || s.status === "active" ? { ...s, status: "done" } : s)),
            );
            if (!bgFinalizedRunIdsRef.current.has(runId)) {
              bgFinalizedRunIdsRef.current.add(runId);
              const md = typeof frame.markdown === "string" ? frame.markdown.trim() : "";
              const sum = typeof frame.summary === "string" ? frame.summary.trim() : "";
              const deliverable = md || sum;
              if (deliverable) {
                const liveCardId = `bg-live-${runId}`;
                setMessages((current) => {
                  const hasLive = current.some((m) => m.id === liveCardId);
                  if (hasLive) {
                    return current.map((m) => (m.id === liveCardId ? createMessage("assistant", deliverable) : m));
                  }
                  return [...current, createMessage("assistant", deliverable)];
                });
              }
            }
            return;
          }

          if (evtType === "agent.run.failed" || evtType === "agent.run.cancelled") {
            const isCancelled = evtType === "agent.run.cancelled";
            pendingAgenticApprovalRef.current = null;
            setCurrentAgentConfirmationStepId(undefined);
            setCurrentAgentApprovalInfo(null);
            const sum = String(frame.summary || (isCancelled ? "Build cancelled." : "Background build failed."));
            setBackgroundBuild((prev) => ({
              runId,
              goal: prev?.goal || goalHint || "",
              status: isCancelled ? "cancelled" : "failed",
              phase: isCancelled ? "cancelled" : "failed",
              headline: sum.slice(0, 120),
              summary: sum,
              filesChanged: prev?.filesChanged,
              previewUrls: prev?.previewUrls,
            }));
            setAgentSteps((current) =>
              current.map((s) =>
                s.status === "pending" || s.status === "active"
                  ? { ...s, status: isCancelled ? "cancelled" : "error", detail: sum }
                  : s,
              ),
            );
            if (!isCancelled && !bgFinalizedRunIdsRef.current.has(runId)) {
              bgFinalizedRunIdsRef.current.add(runId);
              const liveCardId = `bg-live-${runId}`;
              setMessages((current) => {
                const hasLive = current.some((m) => m.id === liveCardId);
                const msg = createMessage("assistant", `### Build Stopped\n${sum}`);
                return hasLive ? current.map((m) => (m.id === liveCardId ? msg : m)) : [...current, msg];
              });
            }
            return;
          }

          setCurrentAgentRunId(runId);
          setBackgroundBuild((prev) => (prev && prev.status !== "running" ? { ...prev, status: "running" } : prev));
          setAgentSteps((current) =>
            runtimeEventToSteps(current, {
              run_id: String(frame.run_id ?? frame.runId ?? runId),
              step_id: typeof frame.step_id === "string" ? frame.step_id : undefined,
              event_type: evtType,
              payload: (frame.payload && typeof frame.payload === "object" ? frame.payload : frame) as Record<string, unknown>,
              sequence: Number(frame.sequence ?? ++bgSeq),
              timestamp: String(frame.timestamp ?? new Date().toISOString()),
            }),
          );
        };

        while (!ac.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const rawLine of lines) {
            const trimmed = rawLine.trim();
            if (!trimmed) continue;
            const jsonStr = trimmed.startsWith("data:") ? trimmed.slice(5).trim() : trimmed;
            if (!jsonStr || jsonStr === "[DONE]") continue;
            try {
              const parsed = JSON.parse(jsonStr);
              if (parsed && typeof parsed === "object") {
                handleFrame(parsed);
              }
            } catch {
              // ignore malformed stream line
            }
          }
        }
        const tail = buffer.trim();
        if (tail && !ac.signal.aborted) {
          const jsonStr = tail.startsWith("data:") ? tail.slice(5).trim() : tail;
          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed && typeof parsed === "object") handleFrame(parsed);
          } catch {}
        }
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return;
        const msg = err instanceof Error ? err.message : "Background build stream interrupted";
        setApprovalError(msg);
      }
    })();
  }, []);

  const cancelBackgroundBuild = useCallback(async () => {
    const targetRunId = backgroundBuildRef.current?.runId ?? currentAgentRunId;
    if (!targetRunId) return;
    bgAbortRef.current?.abort();
    bgAbortRef.current = null;
    await fetch(`/api/v1/agent/agentic-runs/${encodeURIComponent(targetRunId)}/cancel`, {
      method: "POST",
      headers: { ...hinaaIdentityHeaders() },
    }).catch(() => {});
    pendingAgenticApprovalRef.current = null;
    setCurrentAgentConfirmationStepId(undefined);
    setCurrentAgentApprovalInfo(null);
    setApprovalPending(false);
    setApprovalError(null);
    setBackgroundBuild((prev) => (prev ? { ...prev, status: "cancelled", summary: "Build cancelled by user." } : null));
    setAgentSteps((current) =>
      current.map((s) => (s.status === "pending" || s.status === "active" ? { ...s, status: "cancelled" } : s)),
    );
  }, [currentAgentRunId]);

  const confirmCurrentAgentStep = useCallback(async (approved: boolean) => {
    const pendingAgentic = pendingAgenticApprovalRef.current;
    const targetRunId = currentAgentRunId ?? pendingAgentic?.runId;
    const targetStepId = currentAgentConfirmationStepId ?? currentAgentApprovalInfo?.stepId ?? (pendingAgentic ? "approval" : undefined);
    if (!targetRunId || !targetStepId) return;

    setApprovalPending(true);
    setApprovalError(null);

    try {
      if (pendingAgentic && pendingAgentic.runId === targetRunId) {
        const response = await fetch(`/api/v1/agent/agentic-runs/${encodeURIComponent(targetRunId)}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...hinaaIdentityHeaders() },
          body: JSON.stringify({
            approved,
            argumentsHash: pendingAgentic.argumentsHash,
            background: true,
          }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          const errMsg = String(payload?.detail || `Approval failed (${response.status})`);
          if (response.status === 404 || response.status === 409) {
            pendingAgenticApprovalRef.current = null;
            setCurrentAgentConfirmationStepId(undefined);
            setCurrentAgentApprovalInfo(null);
            setApprovalError(null);
            setAgentSteps((current) =>
              current.map((step) =>
                step.id === targetStepId
                  ? { ...step, status: "cancelled" as const, detail: errMsg }
                  : step,
              ),
            );
            setMessages((current) => [
              ...current,
              createMessage("assistant", `Heads up — that approval request was no longer active: ${errMsg}`),
            ]);
          } else {
            setApprovalError(errMsg);
          }
          setState("idle");
          return;
        }
        const res = payload?.result;
        if (approved && (payload?.background === true || res?.status === "running")) {
          pendingAgenticApprovalRef.current = null;
          setCurrentAgentConfirmationStepId(undefined);
          setCurrentAgentApprovalInfo(null);
          setAgentSteps((current) =>
            current.map((step) =>
              step.id === targetStepId
                ? { ...step, status: "done" as const, detail: "Approved — resuming build in background" }
                : step,
            ),
          );
          subscribeBackgroundAgenticRun(targetRunId);
          setState("idle");
          return;
        }
        const nextAppr = res?.status === "awaiting_approval" ? res?.pending_approval : undefined;
        if (nextAppr && nextAppr.arguments_hash) {
          const nextStepId = String(nextAppr.approval_id || "approval");
          const rawNextArgs = (nextAppr.arguments && typeof nextAppr.arguments === "object" ? nextAppr.arguments : {}) as Record<string, unknown>;
          const nextCmd =
            typeof rawNextArgs.command === "string"
              ? rawNextArgs.command
              : typeof rawNextArgs.file_path === "string"
                ? `${String(nextAppr.tool || "tool")} ${rawNextArgs.file_path}`
                : undefined;
          const nextDetail = String(nextAppr.reason || "Awaiting approval");
          pendingAgenticApprovalRef.current = {
            runId: targetRunId,
            argumentsHash: String(nextAppr.arguments_hash),
            tool: typeof nextAppr.tool === "string" ? nextAppr.tool : undefined,
            command: nextCmd,
            detail: nextDetail,
          };
          setCurrentAgentConfirmationStepId(nextStepId);
          setCurrentAgentRunId(targetRunId);
          setCurrentAgentApprovalInfo({
            stepId: nextStepId,
            runId: targetRunId,
            actionName: String(nextAppr.tool || "tool"),
            command: nextCmd,
            detail: nextDetail,
          });
          setAgentSteps((current) => [
            ...current.map((step) =>
              step.id === targetStepId
                ? { ...step, status: "done" as const, detail: "Approved and executed" }
                : step,
            ),
            {
              id: nextStepId,
              label: `Approval required: ${String(nextAppr.tool || "tool")}`,
              status: "pending" as const,
              detail: nextDetail,
              requiresConfirmation: true,
            },
          ]);
          setState("idle");
          return;
        }
        pendingAgenticApprovalRef.current = null;
        setCurrentAgentConfirmationStepId(undefined);
        setCurrentAgentApprovalInfo(null);
        if (!backgroundBuildRef.current || backgroundBuildRef.current.runId !== targetRunId) {
          setCurrentAgentRunId(undefined);
        } else {
          setBackgroundBuild((prev) =>
            prev
              ? {
                  ...prev,
                  status: approved ? "completed" : "cancelled",
                  summary: typeof res?.summary === "string" ? res.summary : prev.summary,
                }
              : prev,
          );
        }
        setAgentSteps((current) =>
          current.map((step) =>
            step.id === targetStepId
              ? {
                  ...step,
                  status: approved ? "done" : "cancelled",
                  detail: approved ? "Approved and executed" : "Declined by user",
                }
              : step,
          ),
        );
        if (res && !bgFinalizedRunIdsRef.current.has(targetRunId)) {
          bgFinalizedRunIdsRef.current.add(targetRunId);
          const videoArts = Array.isArray(res.artifacts)
            ? res.artifacts
                .filter((a: any) => a?.kind === "video" && a?.download_url)
                .map((a: any) => `\n**Rendered MP4:** [Download / Play MP4](${a.download_url})`)
                .join("")
            : "";
          const msg = `### Agentic Approval (${String(res.status || "updated").toUpperCase()})\n${res.summary || "Updated."}${videoArts}`;
          setMessages((current) => [...current, createMessage("assistant", msg)]);
        }
        setState("idle");
        return;
      }

      const response = await fetch(`/api/v1/agent/runs/${encodeURIComponent(targetRunId)}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...hinaaIdentityHeaders() },
        body: JSON.stringify({ stepId: targetStepId, approved }),
      });
      if (!response.ok) {
        const errPayload = await response.json().catch(() => ({}));
        setApprovalError(String(errPayload?.detail || `Confirmation failed (${response.status})`));
        setState("idle");
        return;
      }
      setCurrentAgentConfirmationStepId(undefined);
      setCurrentAgentApprovalInfo(null);
      setAgentSteps((current) =>
        current.map((step) =>
          step.id === targetStepId
            ? {
                ...step,
                status: approved ? "active" : "cancelled",
                detail: approved ? "Approval sent to runtime" : "Rejected by user",
              }
            : step,
        ),
      );
      if (!approved) setState("idle");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Approval request failed";
      setApprovalError(msg);
      setState("idle");
    } finally {
      setApprovalPending(false);
    }
  }, [currentAgentApprovalInfo, currentAgentConfirmationStepId, currentAgentRunId, subscribeBackgroundAgenticRun]);

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
      const historyBase = options?.historyBase;
      const priorMessages = historyBase ?? messagesRef.current;
      setMessages((current) => [
        ...(historyBase ?? current),
        createMessage("user", text, {
          imageUrl: options?.imageUrl,
          attachments: options?.attachments,
        }),
      ]);
      setPartialTranscript("");
      setStreamingText("");
      setActivePlan(undefined);
      const hasLiveBgBuild =
        backgroundBuildRef.current?.status === "running" ||
        backgroundBuildRef.current?.status === "awaiting_approval";
      if (!hasLiveBgBuild && !pendingAgenticApprovalRef.current) {
        setAgentSteps([]);
        setCurrentAgentRunId(undefined);
        setCurrentAgentConfirmationStepId(undefined);
        setCurrentAgentApprovalInfo(null);
        setApprovalError(null);
      }
      setState("thinking");

      let streamRafId: number | null = null;
      let streamTimerId: ReturnType<typeof setTimeout> | null = null;
      let lastStreamFlushTime = 0;
      const cancelStreamSchedules = () => {
        if (streamTimerId !== null) {
          clearTimeout(streamTimerId);
          streamTimerId = null;
        }
        if (streamRafId !== null) {
          if (typeof window !== "undefined" && typeof window.cancelAnimationFrame === "function") {
            window.cancelAnimationFrame(streamRafId);
          }
          streamRafId = null;
        }
      };
      try {
        let rawStreamed = "";
        let streamed = "";
        const speechText = new StreamingSpeechText();
        let isFirstSentence = true;
        let completedPlan: AssistantTurnPlan | undefined;
        let providerLatencyMs: number | undefined;
        const language = resolveTurnLanguage(text, languagePolicy);
        // Snapshot routing for this turn so it can't change mid-stream
        const isMockAllowed = !import.meta.env.PROD || import.meta.env.VITE_ALLOW_MOCK === "true";
        let turnMode = routing.activeMode ?? "claude";
        if (!isMockAllowed && turnMode === "mock") {
          turnMode = "claude";
        }
        const turnModel = routing.activeModel ?? "";
        
        const selectedProvider =
          turnMode !== "mock" || options?.forceBackend || !isMockAllowed
            ? new BackendConversationProvider(turnMode === "mock" ? "claude" : turnMode)
            : provider.current;

        const historyPayload = priorMessages
          .filter(m => (m.role === "user" || m.role === "assistant") && typeof m.text === "string" && m.text.trim().length > 0)
          .slice(-30)
          .map(m => ({ role: m.role, content: m.text }));

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
          persona_mode: options?.persona_mode,
          agenticMode: options?.agenticMode,
          activeAgentRunId: hasLiveBgBuild ? backgroundBuildRef.current?.runId : undefined,
          // An empty resend context is still sent so the server can't fall back to stored turns.
          history: historyPayload.length > 0 || historyBase ? historyPayload : undefined,
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
            const safeStreamed = getSafeAssistantStreamingText(rawStreamed);
            latestStreamedTextRef.current = safeStreamed;
            const looksLikeCodeOrDocDump =
              rawStreamed.includes("```") ||
              rawStreamed.includes("<script") ||
              rawStreamed.length > 4000 ||
              /^#{1,4}\s+/m.test(rawStreamed);
            if (!looksLikeCodeOrDocDump) {
              for (const phrase of speechText.push(safeStreamed)) {
                if (!META_REFLECTION_SPEECH_RE.test(phrase) && options?.onSentenceChunk) {
                  try { options.onSentenceChunk(phrase, isFirstSentence); } catch { /* speech must not block text */ }
                  isFirstSentence = false;
                }
              }
            }

            // Batch streaming deltas smoothly at ~36ms (~28 FPS) to leave 70%+ of main-thread budget for 120 FPS scrolling
            const now = typeof performance !== "undefined" ? performance.now() : Date.now();
            if (streamRafId === null && streamTimerId === null) {
              const timeSinceLastFlush = now - lastStreamFlushTime;
              const flushDeltas = () => {
                streamRafId = null;
                streamTimerId = null;
                if (completedPlan || activeTurnId.current !== turnId) return;
                lastStreamFlushTime = typeof performance !== "undefined" ? performance.now() : Date.now();
                streamed = getSafeAssistantStreamingText(rawStreamed);
                setStreamingText(streamed);
                setState(streamed ? "speaking" : "thinking");
              };

              if (timeSinceLastFlush >= 36) {
                if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
                  streamRafId = window.requestAnimationFrame(flushDeltas);
                } else {
                  flushDeltas();
                }
              } else {
                streamTimerId = setTimeout(() => {
                  streamTimerId = null;
                  if (completedPlan || activeTurnId.current !== turnId) return;
                  if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
                    streamRafId = window.requestAnimationFrame(flushDeltas);
                  } else {
                    flushDeltas();
                  }
                }, Math.max(8, 36 - timeSinceLastFlush));
              }
            }
          } else if (event.type === "plan") {
            cancelStreamSchedules();
            latestStreamedTextRef.current = "";
            const skipTrailingSpeech =
              rawStreamed.includes("```") ||
              rawStreamed.includes("<script") ||
              rawStreamed.length > 4000 ||
              /^#{1,4}\s+/m.test(rawStreamed);
            if (!skipTrailingSpeech) for (const phrase of speechText.flush()) {
              if (!META_REFLECTION_SPEECH_RE.test(phrase) && options?.onSentenceChunk) {
                try { options.onSentenceChunk(phrase, isFirstSentence); } catch { /* non-blocking */ }
                isFirstSentence = false;
              }
            }
            setIsSearching(false);
            setSearchQuery("");
            setStreamingText("");
            completedPlan = event.plan;
            setActivePlan(event.plan);
            const assistantDisplayText = getAssistantDisplayText(serializeAssistantTurn(event.plan));
            try {
              hinaaUIController.handleAssistantResponse(assistantDisplayText);
            } catch {}
            setMessages((current) => [
              ...current,
              createMessage("assistant", assistantDisplayText, {
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
              const p = (event.event.payload ?? {}) as Record<string, unknown>;
              const stepKey = event.event.step_id ?? String(p.approval_id ?? "approval");
              const argHash = String(p.arguments_hash ?? p.argumentsHash ?? "");
              const toolName = typeof p.tool === "string" ? p.tool : "tool";
              const rawArgs = (p.arguments && typeof p.arguments === "object" ? p.arguments : {}) as Record<string, unknown>;
              const cmdStr =
                typeof p.command === "string"
                  ? p.command
                  : typeof rawArgs.command === "string"
                    ? rawArgs.command
                    : typeof rawArgs.file_path === "string"
                      ? `${toolName} ${rawArgs.file_path}`
                      : undefined;
              const detailStr = String(p.reason ?? p.summary ?? "Awaiting explicit approval");
              if (argHash) {
                pendingAgenticApprovalRef.current = {
                  runId: event.event.run_id,
                  argumentsHash: argHash,
                  tool: toolName,
                  command: cmdStr,
                  detail: detailStr,
                };
              }
              setCurrentAgentConfirmationStepId(stepKey);
              setCurrentAgentApprovalInfo({
                stepId: stepKey,
                runId: event.event.run_id,
                actionName: toolName,
                command: cmdStr,
                detail: detailStr,
              });
              setApprovalError(null);
            }
            if (
              event.event.event_type === "agent.run.completed" ||
              event.event.event_type === "agentic.completed" ||
              event.event.event_type === "agent.run.failed" ||
              event.event.event_type === "agent.run.cancelled"
            ) {
              if (!pendingAgenticApprovalRef.current) {
                setCurrentAgentConfirmationStepId(undefined);
                setCurrentAgentApprovalInfo(null);
                if (!backgroundBuildRef.current || backgroundBuildRef.current.runId !== event.event.run_id) {
                  setCurrentAgentRunId(undefined);
                }
              }
            }
            setAgentSteps((current) => runtimeEventToSteps(current, event.event));
          } else if (event.type === "agentic.background") {
            const bgEvt = event as { type: "agentic.background"; runId?: string; run_id?: string; goal?: string };
            const bgRunId = String(bgEvt.runId ?? bgEvt.run_id ?? "");
            if (bgRunId) {
              subscribeBackgroundAgenticRun(bgRunId, String(bgEvt.goal ?? text));
            }
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
        if (!finalizeTurn(turnId, { preservePartial: true, planCompleted: true })) return undefined;
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
        cancelStreamSchedules();
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
        if (request.toolName === "computer_operator" && typeof window !== "undefined" && (window as any).hinaaDesktop) {
          const desk = (window as any).hinaaDesktop;
          const params = (request.parameters || {}) as Record<string, any>;
          const action = params.action;
          const target = params.target || params.content;
          if ((action === "open_application" || action === "open_app") && target && desk.launchApp) {
            void desk.launchApp(target);
          } else if (action === "media_control" && desk.controlMedia) {
            void desk.controlMedia(target || "toggle");
          } else if (action === "youtube_play" && desk.openExternal) {
            void desk.openExternal(`https://www.youtube.com/results?search_query=${encodeURIComponent(target || "")}`);
          } else if (desk.executeAction) {
            void desk.executeAction(params);
          }
        }

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
        if (response.status === 409 && approvalSource === "standing-consent") {
          setMessages((current) => current.map((message) => message.id === messageId ? {
            ...message,
            toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? {
              ...activity,
              status: "pending",
              label: `Approval required: ${request.toolName}`,
            } : activity),
          } : message));
          return;
        }
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
                const pollResponse = await fetch(`/api/v1/tools/poll?job_id=${encodeURIComponent(payload.job_id)}`, { signal: AbortSignal.timeout(12000) });
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
                      model: progress.renderer || progress.provider || existingData.model,
                      note: typeof progress.error === "string" ? progress.error : existingData.note,
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
            setMessages((current) => current.map((message) => message.id === messageId ? {
              ...message,
              toolResults: [...(message.toolResults || []).filter((item) => item.toolName !== request.toolName), { toolName: request.toolName, result: { status: "failed", error: "Image status checks timed out. Check the provider connection and job status before retrying." } }],
              toolActivity: (message.toolActivity || []).map((activity) => activity.id === actionId ? { ...activity, status: "error", label: "Status checks timed out" } : activity),
            } : message));
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
              model: payload.renderer || payload.provider || existingData.model,
              note: typeof payload.error === "string" ? payload.error : existingData.note,
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

        // Autonomously execute UI control actions if returned by tool
        if (outcome.result && typeof outcome.result === "object" && (outcome.result as any).ui_action) {
          hinaaUIController.dispatch((outcome.result as any).ui_action);
        } else if (request.toolName === "ui_control" && request.parameters && (request.parameters as any).action) {
          hinaaUIController.dispatch(request.parameters as any);
        }
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
    liveDeltaBufferRef.current += delta;
    if (liveRafIdRef.current === null) {
      const scheduleFrame =
        typeof window !== "undefined" && typeof window.requestAnimationFrame === "function"
          ? window.requestAnimationFrame
          : (cb: () => void) => setTimeout(cb, 16);
      liveRafIdRef.current = scheduleFrame(() => {
        liveRafIdRef.current = null;
        const buffered = liveDeltaBufferRef.current;
        liveDeltaBufferRef.current = "";
        setStreamingText((current) => current + buffered);
        setState("speaking");
      });
    }
  }, []);

  const applyLivePlan = useCallback((plan: AssistantTurnPlan) => {
    if (liveRafIdRef.current !== null) {
      if (typeof window !== "undefined" && typeof window.cancelAnimationFrame === "function") {
        window.cancelAnimationFrame(liveRafIdRef.current);
      }
      liveRafIdRef.current = null;
    }
    liveDeltaBufferRef.current = "";
    setActivePlan(plan);
    setStreamingText("");
    const displayText = getAssistantDisplayText(serializeAssistantTurn(plan));
    try {
      hinaaUIController.handleAssistantResponse(displayText);
    } catch {}
    setMessages((current) => [
      ...current,
      createMessage("assistant", displayText, {
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
      const isDirectAction =
        request.toolName === "youtube_playback_request" ||
        request.toolName === "spotify_playback_request" ||
        request.toolName === "media_control" ||
        request.toolName === "computer_operator";
      const source = isDirectAction ? "user" : "standing-consent";
      void resolveToolRequest(messageId, request, true, source);
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
    currentAgentApprovalInfo,
    approvalPending,
    approvalError,
    backgroundBuild,
    cancelCurrentAgentRun,
    cancelBackgroundBuild,
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
