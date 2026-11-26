import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, Mic, Rocket, RotateCcw, Send, Sparkles } from "lucide-react";
import type { TranscriptMessage } from "../features/companion/types";
import { ThinkingShimmer } from "../features/chat/components/ThinkingShimmer";
import type { ActivityStep } from "../features/chat/components/AgentActivityCard";
import { AgentActivityFeed } from "../features/chat/components/AgentActivityFeed";
import { LoopAgentRunPanel } from "../features/chat/components/LoopAgentRunPanel";
import { MessageRow } from "../features/chat/components/MessageRow";
import { SlashCommandPalette } from "../features/chat/components/SlashCommandPalette";
import type {
  PendingToolApproval,
  RichActivityStep,
  TurnArtifact,
} from "../features/chat/contracts/agentEvents";
import { usePinnedScroll } from "../features/chat/hooks/usePinnedScroll";
import { useMediaQuery } from "../hooks/useMediaQuery";

const SOFT_CHAR_LIMIT = 2000;
const HARD_CHAR_LIMIT = 8000;

const STARTER_PROMPTS = [
  "Research today's key engineering updates",
  "Inspect and fix bugs in the workspace",
  "Create a cinematic anime typography clip",
  "/plan Launch readiness check",
];

export interface ChatPanelProps {
  messages: TranscriptMessage[];
  streamingText?: string;
  isThinking?: boolean;
  /** Live execution steps; when present they render in ActivityFeedV2 lanes. */
  activitySteps?: Array<ActivityStep | RichActivityStep>;
  thought?: string;
  thoughtSummary?: string | null;
  artifacts?: TurnArtifact[];
  pendingApproval?: PendingToolApproval | null;
  onApprove?: (approval: PendingToolApproval) => void;
  onReject?: (approval: PendingToolApproval) => void;
  onRegenerate?: (message: TranscriptMessage) => void;
  onEditMessage?: (message: TranscriptMessage, nextText: string) => void;
  input: string;
  onInputChange: (val: string) => void;
  onSend: (text?: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  onStartVoice?: () => void;
  /** Live loop task id; when set the panel streams the agent run via SSE. */
  agentRunTaskId?: string | null;
}

/**
 * ChatPanel v3 — virtualized transcript, token-driven surfaces, pinned scroll,
 * parallel execution rail (desktop >=1024px) / inline card (mobile), shimmer,
 * /slash + @artifact command palette, and autonomous Agent Run loop panel.
 */
export function ChatPanel({
  messages,
  streamingText,
  isThinking = false,
  activitySteps = [],
  thought,
  thoughtSummary,
  artifacts = [],
  pendingApproval = null,
  onApprove,
  onReject,
  onRegenerate,
  onEditMessage,
  input,
  onInputChange,
  onSend,
  onStop,
  disabled = false,
  onStartVoice,
  agentRunTaskId = null,
}: ChatPanelProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [longWait, setLongWait] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [agentGoal, setAgentGoal] = useState("");
  const [agentVerify, setAgentVerify] = useState("");
  const [launching, setLaunching] = useState(false);
  const [liveTaskId, setLiveTaskId] = useState<string | null>(agentRunTaskId ?? null);
  const isDesktop = useMediaQuery("(min-width: 1024px)", true);

  useEffect(() => {
    if (agentRunTaskId !== null && agentRunTaskId !== undefined) {
      setLiveTaskId(agentRunTaskId);
    }
  }, [agentRunTaskId]);

  const startAgentRun = async () => {
    const goal = agentGoal.trim();
    if (!goal || launching) return;
    setLaunching(true);
    try {
      const res = await fetch("/api/loop/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal_title: goal,
          verification_command: agentVerify.trim()
            ? agentVerify.trim().split(/\s+/)
            : ["true"],
          max_turns: 10,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as { task_id?: string };
        if (data.task_id) {
          setLiveTaskId(data.task_id);
          setAgentMode(false);
        }
      }
    } finally {
      setLaunching(false);
    }
  };

  const hasActivity =
    activitySteps.length > 0 ||
    Boolean(thought?.trim()) ||
    artifacts.length > 0 ||
    pendingApproval !== null;

  const { pinned, unreadCount, scrollToBottom } = usePinnedScroll({
    scrollRef: scrollContainerRef,
    itemCount: messages.length,
    streamingKey: streamingText?.length ?? 0,
  });

  const getScrollElement = useCallback(() => scrollContainerRef.current, []);
  const estimateSize = useCallback(() => 96, []);
  const observeElementRect = useCallback(
    (
      instance: { scrollElement: HTMLDivElement | null },
      cb: (rect: { width: number; height: number }) => void,
    ) => {
      const el = instance.scrollElement;
      if (!el) return;
      const emit = () => {
        const rect = el.getBoundingClientRect();
        cb({
          width: rect.width > 0 ? rect.width : el.clientWidth || 800,
          height: rect.height > 0 ? rect.height : el.clientHeight || 600,
        });
      };
      emit();
      if (typeof ResizeObserver === "undefined") return;
      const ro = new ResizeObserver(emit);
      ro.observe(el);
      return () => ro.disconnect();
    },
    [],
  );

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement,
    estimateSize,
    overscan: 10,
    initialRect: { width: 800, height: 600 },
    observeElementRect,
  });

  const measureElementSafe = useCallback(
    (el: HTMLDivElement | null) => {
      if (el && el.getBoundingClientRect().height > 0) {
        virtualizer.measureElement(el);
      }
    },
    [virtualizer],
  );

  const virtualItems = virtualizer.getVirtualItems();
  const fallbackMessages =
    virtualItems.length === 0 && messages.length > 0 ? messages.slice(-24) : [];

  const paletteState = useMemo(() => {
    const slashMatch = /(?:^|\s)\/([A-Za-z0-9_-]*)$/.exec(input);
    if (slashMatch) {
      return { mode: "slash" as const, query: slashMatch[1], fullToken: `/${slashMatch[1]}` };
    }
    const mentionMatch = /(?:^|\s)@([A-Za-z0-9._-]*)$/.exec(input);
    if (mentionMatch) {
      return { mode: "mention" as const, query: mentionMatch[1], fullToken: `@${mentionMatch[1]}` };
    }
    return { mode: null, query: "", fullToken: "" };
  }, [input]);

  const handlePaletteSelect = useCallback(
    (insertion: string) => {
      if (!paletteState.fullToken) {
        onInputChange(input + insertion);
        return;
      }
      const idx = input.lastIndexOf(paletteState.fullToken);
      const next =
        idx >= 0
          ? `${input.slice(0, idx)}${insertion}${input.slice(idx + paletteState.fullToken.length)}`
          : `${input} ${insertion}`;
      onInputChange(next);
    },
    [input, onInputChange, paletteState.fullToken],
  );

  const overHardLimit = input.length > HARD_CHAR_LIMIT;
  const nearSoftLimit = input.length >= SOFT_CHAR_LIMIT;
  const canSend = Boolean(input.trim()) && !disabled && !overHardLimit;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  const escalate = useCallback(() => setLongWait(true), []);

  const streamingMessage = useMemo<TranscriptMessage | null>(
    () =>
      streamingText
        ? {
            id: "__streaming__",
            role: "assistant",
            text: streamingText,
            createdAt: "",
          }
        : null,
    [streamingText],
  );

  return (
    <section
      data-testid="chat-panel"
      className="flex-1 h-full flex min-w-0 min-h-0 border rounded-[var(--radius-card)] overflow-hidden"
      style={{
        background: "var(--bg-glass)",
        borderColor: "var(--border-subtle)",
        color: "var(--text-primary)",
        boxShadow: "var(--shadow-float)",
      }}
    >
      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative">
        <div
          ref={scrollContainerRef}
          data-testid="chat-transcript-scroll"
          className="flex-1 overflow-y-auto min-h-0 p-4"
        >
          {messages.length === 0 && !streamingText && !isThinking && !hasActivity && (
            <div className="h-full flex flex-col items-center justify-center text-center p-6">
              <div
                className="w-12 h-12 rounded-2xl flex items-center justify-center mb-3"
                style={{ background: "var(--accent-soft)", color: "var(--accent-primary)" }}
              >
                <Sparkles size={24} />
              </div>
              <h3 className="font-semibold text-sm mb-1" style={{ color: "var(--text-primary)" }}>
                HINAA Workspace Active
              </h3>
              <p className="text-xs max-w-md mb-4" style={{ color: "var(--text-muted)" }}>
                Ask anything, type <code style={{ fontFamily: "var(--font-mono)" }}>/</code> for quick actions, or launch parallel execution with live tool tracking.
              </p>
              <div className="flex flex-wrap justify-center gap-2 max-w-xl">
                {STARTER_PROMPTS.map((starter) => (
                  <button
                    key={starter}
                    type="button"
                    onClick={() => onSend(starter)}
                    className="px-3 py-1.5 rounded-[var(--radius-pill)] border text-xs font-medium cursor-pointer transition-opacity hover:opacity-90"
                    style={{
                      borderColor: "var(--border-subtle)",
                      background: "var(--bg-elevated)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {starter}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.length > 0 && (
            <div
              data-testid="chat-virtual-canvas"
              style={{
                height: `${virtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
              }}
            >
              {virtualItems.length > 0
                ? virtualItems.map((vItem) => {
                    const msg = messages[vItem.index];
                    if (!msg) return null;
                    return (
                      <div
                        key={msg.id}
                        data-index={vItem.index}
                        ref={measureElementSafe}
                        style={{
                          position: "absolute",
                          top: 0,
                          left: 0,
                          width: "100%",
                          transform: `translateY(${vItem.start}px)`,
                          paddingBottom: 14,
                        }}
                      >
                        <MessageRow
                          message={msg}
                          onRegenerate={onRegenerate}
                          onEdit={onEditMessage}
                        />
                      </div>
                    );
                  })
                : fallbackMessages.map((msg) => (
                    <div key={msg.id} style={{ paddingBottom: 14 }}>
                      <MessageRow
                        message={msg}
                        onRegenerate={onRegenerate}
                        onEdit={onEditMessage}
                      />
                    </div>
                  ))}
            </div>
          )}

          {!isDesktop && hasActivity && (
            <div className="my-3">
              <AgentActivityFeed
                steps={activitySteps}
                thought={thought}
                thoughtSummary={thoughtSummary}
                artifacts={artifacts}
                pendingApproval={pendingApproval}
                onApprove={onApprove}
                onReject={onReject}
                variant="inline"
                isActive={isThinking}
              />
            </div>
          )}

          {streamingMessage && (
            <div className="mt-3">
              <MessageRow message={streamingMessage} isStreaming />
            </div>
          )}

          {isThinking && activitySteps.length === 0 && (
            <div className="mt-2">
              <ThinkingShimmer
                active
                stage={
                  longWait
                    ? "Running tools and verifying output…"
                    : "Hina is thinking"
                }
                onEscalate={escalate}
              />
            </div>
          )}
        </div>

        {!pinned && (
          <button
            type="button"
            data-testid="jump-to-latest-btn"
            onClick={() => scrollToBottom("smooth")}
            className="absolute bottom-24 right-5 z-10 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-pill)] border text-xs font-semibold cursor-pointer"
            style={{
              background: "var(--bg-elevated)",
              borderColor: "var(--border-strong)",
              color: "var(--text-primary)",
              boxShadow: "var(--shadow-float)",
            }}
          >
            <ArrowDown size={13} />
            <span>
              Jump to latest{unreadCount > 0 ? ` (${unreadCount})` : ""}
            </span>
          </button>
        )}

        {liveTaskId && (
          <div className="px-4 pb-2 shrink-0">
            <LoopAgentRunPanel
              taskId={liveTaskId}
              onFinished={() => setLiveTaskId((id) => id)}
            />
          </div>
        )}

        <div
          className="border-t p-3 shrink-0"
          style={{ borderColor: "var(--border-subtle)", background: "var(--bg-glass)" }}
        >
          <SlashCommandPalette
            mode={paletteState.mode}
            query={paletteState.query}
            artifacts={artifacts}
            onSelect={handlePaletteSelect}
          />
          {agentMode ? (
            <div
              className="border rounded-xl p-2 space-y-2"
              style={{
                background: "var(--bg-elevated)",
                borderColor: "var(--border-subtle)",
              }}
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 px-1 text-xs font-medium" style={{ color: "var(--accent-primary)" }}>
                  <Rocket size={13} aria-hidden /> Agent Run
                </span>
                <button
                  type="button"
                  onClick={() => setAgentMode(false)}
                  title="Back to chat"
                  className="p-1 rounded-lg cursor-pointer"
                  style={{ color: "var(--text-muted)" }}
                >
                  <RotateCcw size={13} aria-hidden />
                </button>
              </div>
              <textarea
                value={agentGoal}
                onChange={(e) => setAgentGoal(e.target.value)}
                placeholder="Goal for Hina to work on unattended (e.g. “Fix the failing login test”)…"
                rows={2}
                className="w-full resize-none bg-transparent text-xs outline-none px-1 py-1"
                style={{ color: "var(--text-primary)" }}
              />
              <input
                type="text"
                value={agentVerify}
                onChange={(e) => setAgentVerify(e.target.value)}
                placeholder="Verification command (e.g. “pnpm test -- --run”). Defaults to a no-op check."
                className="w-full bg-transparent text-[11px] outline-none px-1 py-1 border-t"
                style={{ color: "var(--text-primary)", borderColor: "var(--border-subtle)" }}
              />
              <button
                type="button"
                onClick={startAgentRun}
                disabled={!agentGoal.trim() || launching}
                className="w-full flex items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-white hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer"
                style={{ background: "var(--accent-primary)" }}
              >
                <Rocket size={13} aria-hidden />
                {launching ? "Launching…" : "Launch agent run"}
              </button>
            </div>
          ) : (
            <div
              className="flex items-end gap-2 border rounded-xl p-2 transition-colors"
              style={{
                background: "var(--bg-elevated)",
                borderColor: overHardLimit ? "var(--status-err)" : "var(--border-subtle)",
              }}
            >
              <textarea
                aria-label="Message input"
                value={input}
                onChange={(e) => onInputChange(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={disabled}
                placeholder="Message Hinaa… (/ for actions, @ for files, Enter to send)"
                rows={1}
                className="flex-1 max-h-32 resize-none bg-transparent text-xs outline-none px-1 py-1"
                style={{ color: "var(--text-primary)" }}
              />

              <div className="flex items-center gap-1.5 shrink-0">
                {nearSoftLimit && (
                  <span
                    data-testid="char-limit-indicator"
                    className="text-[10px] font-mono px-1.5"
                    style={{
                      color: overHardLimit ? "var(--status-err)" : "var(--status-warn)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {input.length}/{HARD_CHAR_LIMIT}
                  </span>
                )}

                <button
                  type="button"
                  onClick={() => setAgentMode(true)}
                  aria-label="Agent Run mode"
                  title="Agent Run mode — give Hina an unattended goal"
                  className="p-1.5 rounded-lg cursor-pointer"
                  style={{ color: "var(--text-muted)" }}
                >
                  <Rocket size={15} />
                </button>

                {onStartVoice && (
                  <button
                    type="button"
                    onClick={onStartVoice}
                    aria-label="Live Voice Mode"
                    title="Live Voice Mode"
                    className="p-1.5 rounded-lg cursor-pointer"
                    style={{ color: "var(--text-muted)" }}
                  >
                    <Mic size={15} />
                  </button>
                )}

                {isThinking && onStop ? (
                  <button
                    type="button"
                    onClick={onStop}
                    aria-label="Stop generation"
                    title="Stop generation"
                    className="p-1.5 rounded-lg cursor-pointer"
                    style={{ background: "var(--status-err)", color: "#ffffff" }}
                  >
                    <span className="block w-3 h-3 rounded-[2px] bg-white" aria-hidden="true" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      if (canSend) onSend();
                    }}
                    disabled={!canSend}
                    aria-label="Send message"
                    className="p-1.5 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    style={{ background: "var(--accent-primary)", color: "#ffffff" }}
                  >
                    <Send size={14} />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {isDesktop && hasActivity && (
        <AgentActivityFeed
          steps={activitySteps}
          thought={thought}
          thoughtSummary={thoughtSummary}
          artifacts={artifacts}
          pendingApproval={pendingApproval}
          onApprove={onApprove}
          onReject={onReject}
          variant="rail"
          isActive={isThinking}
        />
      )}
    </section>
  );
}
