import React, { useRef, useEffect, useState, useCallback } from "react";
import { Send, Sparkles, Mic, Bot, User, Rocket, RotateCcw } from "lucide-react";
import type { TranscriptMessage } from "../features/companion/types";
import { ThinkingShimmer } from "../features/chat/components/ThinkingShimmer";
import { ActivityFeedV2 } from "../features/chat/components/ActivityFeedV2";
import { LoopAgentRunPanel } from "../features/chat/components/LoopAgentRunPanel";
import type { ActivityStep } from "../features/chat/components/AgentActivityCard";

export interface ChatPanelProps {
  messages: TranscriptMessage[];
  streamingText?: string;
  isThinking?: boolean;
  /** Live execution steps; when present they render as Activity Feed v2 lanes. */
  activitySteps?: ActivityStep[];
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
 * ChatPanel v2 — the redesigned chat surface.
 *
 * Layered bottom-to-top: Activity Feed lanes (parallel tool work), the
 * streaming delta bubble, a Thinking Shimmer between send and first token,
 * then the transcript and composer. The shimmer escalates to a richer
 * indicator message if Hina is quiet for too long, so silence is never
 * mistaken for a freeze.
 */
export function ChatPanel({
  messages,
  streamingText,
  isThinking,
  activitySteps,
  input,
  onInputChange,
  onSend,
  onStop,
  disabled = false,
  onStartVoice,
  agentRunTaskId = null,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [longWait, setLongWait] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [agentGoal, setAgentGoal] = useState("");
  const [agentVerify, setAgentVerify] = useState("");
  const [launching, setLaunching] = useState(false);
  const [liveTaskId, setLiveTaskId] = useState<string | null>(agentRunTaskId ?? null);

  useEffect(() => {
    if (agentRunTaskId !== null && agentRunTaskId !== undefined) setLiveTaskId(agentRunTaskId);
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, isThinking, activitySteps]);

  useEffect(() => {
    if (!isThinking) {
      setLongWait(false);
      return;
    }
    const timer = setTimeout(() => setLongWait(true), 6000);
    return () => clearTimeout(timer);
  }, [isThinking]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !disabled) {
        onSend();
      }
    }
  };

  const escalate = useCallback(() => setLongWait(true), []);
  const hasActivity = (activitySteps?.length ?? 0) > 0;

  return (
    <section className="flex-1 h-full flex flex-col min-w-0 min-h-0 bg-frost/90 backdrop-blur-md border border-glass-border rounded-xl shadow-soft overflow-hidden">
      {/* ── 1. Message Stream ── */}
      <div className="flex-1 overflow-y-auto min-h-0 p-4 space-y-4">
        {messages.length === 0 && !streamingText && !isThinking && !hasActivity && (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-text-muted">
            <div className="w-12 h-12 rounded-2xl bg-brand-100 flex items-center justify-center text-accent mb-3">
              <Sparkles size={24} />
            </div>
            <h3 className="font-semibold text-text-primary text-sm mb-1">
              HINAA OS Active
            </h3>
            <p className="text-xs max-w-sm">
              Your autonomous AI character and engineering partner. Send a task, ask questions, or enable live voice.
            </p>
          </div>
        )}

        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              className={`flex gap-3 max-w-3xl min-w-0 ${
                isUser ? "ml-auto flex-row-reverse" : "mr-auto"
              }`}
            >
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs shadow-xs ${
                  isUser
                    ? "bg-text-primary text-white"
                    : "bg-accent text-white"
                }`}
              >
                {isUser ? <User size={14} /> : <Bot size={14} />}
              </div>

              <div
                className={`p-3 rounded-2xl text-xs leading-relaxed break-words min-w-0 shadow-xs ${
                  isUser
                    ? "bg-text-primary text-white rounded-tr-none"
                    : "bg-white text-text-primary border border-glass-border rounded-tl-none"
                }`}
              >
                {msg.text}
              </div>
            </div>
          );
        })}

        {/* Activity Feed v2 — parallel tool lanes */}
        {hasActivity && (
          <div className="max-w-3xl mr-auto min-w-0">
            <ActivityFeedV2 steps={activitySteps!} />
          </div>
        )}

        {/* Live streaming delta bubble */}
        {streamingText && (
          <div className="flex gap-3 max-w-3xl min-w-0 mr-auto">
            <div className="w-7 h-7 rounded-lg bg-accent text-white flex items-center justify-center flex-shrink-0 text-xs shadow-xs">
              <Bot size={14} />
            </div>
            <div className="p-3 rounded-2xl bg-white text-text-primary border border-glass-border rounded-tl-none text-xs leading-relaxed break-words min-w-0 shadow-xs">
              {streamingText}
              <span className="inline-block w-1.5 h-3 ml-1 bg-accent animate-pulse" />
            </div>
          </div>
        )}

        {/* Thinking Shimmer — shown while Hina works, escalating on long waits */}
        {isThinking && !hasActivity && (
          <ThinkingShimmer
            active
            stage={longWait ? "Still working — running tools and verifying results…" : "Hina is thinking"}
            onEscalate={escalate}
          />
        )}

        {/* Spacing element ensuring bottom clearance before input container */}
        <div ref={messagesEndRef} className="h-2 flex-shrink-0" />
      </div>

      {/* ── 1b. Live agent run (autonomous loop) ── */}
      {liveTaskId && (
        <div className="px-4 pb-2 flex-shrink-0">
          <LoopAgentRunPanel
            taskId={liveTaskId}
            onFinished={() => setLiveTaskId((id) => id)}
          />
        </div>
      )}

      {/* ── 2. Composer ── */}
      <div className="border-t border-glass-border p-3 bg-frost/50 backdrop-blur-md flex-shrink-0">
        {agentMode ? (
          <div className="bg-white border border-glass-border rounded-xl p-2 shadow-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 px-1 text-xs font-medium text-accent">
                <Rocket size={13} aria-hidden /> Agent
 Run
              </span>
              <button
                type="button"
                onClick={() => setAgentMode(false)}
                title="Back to chat"
                className="p-1 rounded-lg text-text-muted hover:text-accent hover:bg-brand-100 transition-colors"
              >
                <RotateCcw size={13} aria-hidden />
              </button>
            </div>
            <textarea
              value={agentGoal}
              onChange={(e) => setAgentGoal(e.target.value)}
              placeholder="Goal for Hina to work on unattended (e.g. “Fix the failing login test”)…"
              rows={2}
              className="w-full resize-none bg-transparent text-xs text-text-primary placeholder:text-text-muted outline-hidden px-1 py-1"
            />
            <input
              type="text"
              value={agentVerify}
              onChange={(e) => setAgentVerify(e.target.value)}
              placeholder="Verification command (e.g. “pnpm test -- --run”). Defaults to a no-op check."
              className="w-full bg-transparent text-[11px] text-text-primary placeholder:text-text-muted outline-hidden px-1 py-1 border-t border-glass-border"
            />
            <button
              type="button"
              onClick={startAgentRun}
              disabled={!agentGoal.trim() || launching}
              className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-accent px-2 py-1.5 text-xs text-white hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <Rocket size={13} aria-hidden />
              {launching ? "Launching…" : "Launch agent run"}
            </button>
          </div>
        ) : (
        <div className="flex items-end gap-2 bg-white border border-glass-border rounded-xl p-2 shadow-xs focus-within:border-accent transition-colors">
          <textarea
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Type a message or command (Enter to send, Shift+Enter for newline)…"
            rows={1}
            className="flex-1 max-h-32 resize-none bg-transparent text-xs text-text-primary placeholder:text-text-muted outline-hidden px-1 py-1"
          />

          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              type="button"
              onClick={() => setAgentMode(true)}
              title="Agent Run mode — give Hina an unattended goal"
              className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-brand-100 transition-colors"
            >
              <Rocket size={15} />
            </button>
            {onStartVoice && (
              <button
                type="button"
                onClick={onStartVoice}
                title="Live Voice Mode"
                className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-brand-100 transition-colors"
              >
                <Mic size={15} />
              </button>
            )}

            {isThinking && onStop ? (
              <button
                type="button"
                onClick={onStop}
                title="Stop generation"
                className="p-1.5 rounded-lg bg-red-500 text-white hover:opacity-90 transition-all shadow-xs"
              >
                <span className="block w-3 h-3 rounded-[2px] bg-white" aria-hidden />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  if (input.trim() && !disabled) {
                    onSend();
                  }
                }}
                disabled={!input.trim() || disabled}
                className="p-1.5 rounded-lg bg-accent text-white hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-xs"
              >
                <Send size={14} />
              </button>
            )}
          </div>
        </div>
        )}
      </div>
    </section>
  );
}
