import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, Check, Copy, Pencil, RotateCcw, User } from "lucide-react";
import type { TranscriptMessage } from "../../companion/types";

export interface MessageRowProps {
  message: TranscriptMessage;
  isStreaming?: boolean;
  onCopy?: (text: string) => void;
  onRegenerate?: (message: TranscriptMessage) => void;
  onEdit?: (message: TranscriptMessage, nextText: string) => void;
}

function CodeBlock({ className, children }: { className?: string; children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  const codeText = String(children ?? "").replace(/\n$/, "");
  const langMatch = /language-([\w-]+)/.exec(className || "");
  const lang = langMatch?.[1] || "";

  if (!className && !codeText.includes("\n")) {
    return (
      <code
        className="px-1 py-0.5 rounded text-[11px]"
        style={{
          fontFamily: "var(--font-mono)",
          background: "var(--bg-subtle)",
          color: "var(--accent-primary)",
        }}
      >
        {children}
      </code>
    );
  }

  return (
    <div
      className="my-2 rounded-xl border overflow-hidden"
      style={{
        borderColor: "var(--border-subtle)",
        background: "var(--bg-canvas)",
      }}
    >
      <div
        className="flex items-center justify-between px-2.5 py-1 border-b text-[10px]"
        style={{
          borderColor: "var(--border-subtle)",
          color: "var(--text-muted)",
          fontFamily: "var(--font-mono)",
        }}
      >
        <span>{lang || "code"}</span>
        <button
          type="button"
          aria-label="Copy code block"
          onClick={() => {
            void navigator.clipboard?.writeText(codeText);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1200);
          }}
          className="inline-flex items-center gap-1 hover:opacity-80 cursor-pointer"
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre
        className="p-2.5 overflow-x-auto text-[11px] leading-relaxed m-0"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        <code>{codeText}</code>
      </pre>
    </div>
  );
}

export const MessageRow = React.memo(function MessageRow({
  message,
  isStreaming = false,
  onCopy,
  onRegenerate,
  onEdit,
}: MessageRowProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.text);

  const handleCopyMessage = () => {
    void navigator.clipboard?.writeText(message.text);
    onCopy?.(message.text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  return (
    <article
      data-testid={`message-row-${message.role}`}
      className={`group flex gap-3 max-w-3xl min-w-0 ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}
    >
      <div
        aria-hidden="true"
        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs"
        style={{
          background: isUser ? "var(--chat-user-bubble-bg)" : "var(--accent-primary)",
          color: "#ffffff",
        }}
      >
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      <div className="min-w-0 flex flex-col gap-1 max-w-full">
        <div
          className={`px-3.5 py-2.5 rounded-2xl text-[13px] leading-relaxed break-words min-w-0 border ${
            isUser ? "rounded-tr-none" : "rounded-tl-none"
          }`}
          style={
            isUser
              ? {
                  background: "var(--chat-user-bubble-bg)",
                  color: "var(--chat-user-bubble-text)",
                  borderColor: "transparent",
                }
              : {
                  background: "var(--chat-assistant-bubble-bg)",
                  color: "var(--chat-assistant-bubble-text)",
                  borderColor: "var(--border-subtle)",
                }
          }
        >
          {editing ? (
            <div className="flex flex-col gap-2 min-w-[220px]">
              <textarea
                aria-label="Edit message text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                className="w-full rounded-lg p-2 text-xs bg-black/20 border border-white/20 text-inherit outline-none"
              />
              <div className="flex justify-end gap-1.5">
                <button
                  type="button"
                  onClick={() => {
                    setEditing(false);
                    setDraft(message.text);
                  }}
                  className="px-2 py-0.5 rounded text-[11px] opacity-80 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditing(false);
                    if (draft.trim() && draft.trim() !== message.text) {
                      onEdit?.(message, draft.trim());
                    }
                  }}
                  className="px-2 py-0.5 rounded text-[11px] font-semibold cursor-pointer"
                  style={{ background: "var(--accent-primary)", color: "#ffffff" }}
                >
                  Save
                </button>
              </div>
            </div>
          ) : isUser ? (
            <p className="m-0 whitespace-pre-wrap">{message.text}</p>
          ) : (
            <div className="prose-chat max-w-none [&>p]:my-1 [&>ul]:my-1 [&>ol]:my-1">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code: ({ className, children }) => (
                    <CodeBlock className={className}>{children}</CodeBlock>
                  ),
                }}
              >
                {message.text}
              </ReactMarkdown>
              {isStreaming && (
                <span
                  aria-hidden="true"
                  className="inline-block w-1.5 h-3.5 ml-1 align-middle animate-pulse"
                  style={{ background: "var(--accent-primary)" }}
                />
              )}
            </div>
          )}
        </div>

        <div
          className={`flex items-center gap-2 text-[10px] opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity ${
            isUser ? "justify-end" : "justify-start"
          }`}
          style={{ color: "var(--text-muted)" }}
        >
          <button
            type="button"
            aria-label="Copy message"
            onClick={handleCopyMessage}
            className="inline-flex items-center gap-1 hover:underline cursor-pointer"
          >
            {copied ? <Check size={10} /> : <Copy size={10} />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
          {!isUser && onRegenerate && !isStreaming && (
            <button
              type="button"
              aria-label="Regenerate response"
              onClick={() => onRegenerate(message)}
              className="inline-flex items-center gap-1 hover:underline cursor-pointer"
            >
              <RotateCcw size={10} />
              <span>Regenerate</span>
            </button>
          )}
          {isUser && onEdit && !editing && (
            <button
              type="button"
              aria-label="Edit message"
              onClick={() => {
                setDraft(message.text);
                setEditing(true);
              }}
              className="inline-flex items-center gap-1 hover:underline cursor-pointer"
            >
              <Pencil size={10} />
              <span>Edit</span>
            </button>
          )}
        </div>
      </div>
    </article>
  );
});
