import React, { useRef, useEffect } from "react";
import { Send, Sparkles, Mic, Paperclip, Bot, User } from "lucide-react";
import type { TranscriptMessage } from "../features/companion/types";

export interface ChatPanelProps {
  messages: TranscriptMessage[];
  streamingText?: string;
  isThinking?: boolean;
  input: string;
  onInputChange: (val: string) => void;
  onSend: (text?: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  onStartVoice?: () => void;
}

export function ChatPanel({
  messages,
  streamingText,
  isThinking,
  input,
  onInputChange,
  onSend,
  onStop,
  disabled = false,
  onStartVoice,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom as new tokens arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, isThinking]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !disabled) {
        onSend();
      }
    }
  };

  return (
    <section className="flex-1 h-full flex flex-col min-w-0 min-h-0 bg-frost/90 backdrop-blur-md border border-glass-border rounded-xl shadow-soft overflow-hidden">
      {/* ── 1. Message Stream (strictly overflow-y-auto, min-h-0) ── */}
      <div className="flex-1 overflow-y-auto min-h-0 p-4 space-y-4">
        {messages.length === 0 && !streamingText && (
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

        {/* Thinking indicator */}
        {isThinking && (
          <div className="flex items-center gap-2 text-xs text-text-muted italic px-2">
            <span className="w-2 h-2 rounded-full bg-accent animate-ping" />
            <span>Hina is analyzing intent and planning execution…</span>
          </div>
        )}

        {/* Spacing element ensuring bottom clearance before input container */}
        <div ref={messagesEndRef} className="h-2 flex-shrink-0" />
      </div>

      {/* ── 2. Dedicated Input Row (sibling border-t container, flex-shrink-0, independent padding) ── */}
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
          </div>
        </div>
      </div>
    </section>
  );
}
