import React, { useRef, useEffect, useState, useCallback } from "react";
import { Send, Sparkles, Mic, Bot, User } from "lucide-react";
import type { TranscriptMessage } from "../features/companion/types";
import { ThinkingShimmer } from "../features/chat/components/ThinkingShimmer";
import { ActivityFeedV2 } from "../features/chat/components/ActivityFeedV2";
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
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [longWait, setLongWait] = useState(false);

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

      {/* ── 2. Composer ── */}
      <div className="border-t border-glass-border p-3 bg-frost/50 backdrop-blur-md flex-shrink-0">
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
      </div>
    </section>
  );
}
