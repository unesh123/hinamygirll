import { memo } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Copy, Check, RotateCcw } from "lucide-react";
import { useState, useCallback, useRef, useEffect } from "react";
import { ResponseRenderer } from "../../components/ui/ResponseRenderer";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp?: string;
}

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
  onRetry?: () => void;
}

export const ChatMessage = memo(function ChatMessage({
  message,
  isStreaming = false,
  onRetry,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current); }, []);
  const reducedMotion = useReducedMotion();

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopied(true);
      setCopyFailed(false);
    } catch {
      setCopied(false);
      setCopyFailed(true);
    }
    if (copyTimer.current) clearTimeout(copyTimer.current);
    copyTimer.current = setTimeout(() => { setCopied(false); setCopyFailed(false); }, 2000);
  }, [message.text]);

  const isUser = message.role === "user";

  return (
    <motion.div
      initial={reducedMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
      className={`sakura-message ${isUser ? "sakura-message--user" : "sakura-message--assistant"}`}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1-5)",
        maxWidth: "var(--max-width-chat)",
        width: "100%",
        alignSelf: isUser ? "flex-end" : "flex-start",
      }}
    >
      {/* Message content */}
      <div
        className={isUser ? "sakura-msg-user" : "sakura-msg-assistant"}
        style={{
          padding: isUser ? "var(--space-3) var(--space-4)" : "var(--space-2) 0",
          borderRadius: isUser ? "var(--radius-xl) var(--radius-xl) var(--radius-xs) var(--radius-xl)" : "var(--radius-md)",
          background: isUser ? "var(--accent-pale)" : "transparent",
          color: isUser ? "var(--text-primary)" : "var(--text-primary)",
          fontSize: "var(--text-base)",
          lineHeight: "var(--leading-relaxed)",
          border: isUser ? "1px solid var(--border-subtle)" : "none",
          position: "relative",
        }}
      >
        {!isUser && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            marginBottom: "var(--space-1)",
          }}>
            <div style={{
              width: 22,
              height: 22,
              borderRadius: "var(--radius-sm)",
              background: "linear-gradient(135deg, var(--accent), var(--peach))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
              fontSize: "var(--text-xs)",
              fontWeight: 800,
              fontFamily: "var(--font-retro)",
              flexShrink: 0,
            }}>
              H
            </div>
            <span style={{
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              color: "var(--text-secondary)",
            }}>
              HINAA
            </span>
          </div>
        )}

        {/* Rendered content */}
        <div className="sakura-msg-content">
          {isUser ? <div style={{ whiteSpace: "pre-wrap" }}>{message.text}</div> : <ResponseRenderer content={message.text} />}
        </div>

        {/* Streaming cursor */}
        {isStreaming && (
          <span className="sakura-streaming-cursor" />
        )}
      </div>

      {/* Actions */}
      {!isUser && !isStreaming && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-1)",
          paddingLeft: "var(--space-1)",
        }}>
          <MsgActionBtn onClick={handleCopy} title="Copy">
            {copied ? <Check size={13} /> : <Copy size={13} />}
          </MsgActionBtn>
          <span role="status" className="response-sr-only">{copied ? "Message copied" : copyFailed ? "Unable to copy message" : ""}</span>
          {onRetry && (
            <MsgActionBtn onClick={onRetry} title="Retry">
              <RotateCcw size={13} />
            </MsgActionBtn>
          )}
        </div>
      )}

      <style>{`
        .sakura-streaming-cursor {
          display: inline-block;
          width: 2px;
          height: 1.1em;
          background: var(--accent);
          margin-left: 2px;
          vertical-align: text-bottom;
          border-radius: 1px;
          animation: sakura-cursor-blink 0.8s ease-in-out infinite;
        }

        @keyframes sakura-cursor-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.2; }
        }

        .sakura-msg-content h1 { font-size: var(--text-xl); margin: 0.8em 0 0.4em; font-weight: 700; }
        .sakura-msg-content h2 { font-size: var(--text-lg); margin: 0.8em 0 0.4em; font-weight: 700; }
        .sakura-msg-content h3 { font-size: var(--text-md); margin: 0.6em 0 0.3em; font-weight: 600; }
        .sakura-msg-content p { margin-bottom: 0.6em; }
        .sakura-msg-content ul, .sakura-msg-content ol { padding-left: 1.4em; margin-bottom: 0.6em; }
        .sakura-msg-content li { margin-bottom: 0.25em; }
        .sakura-msg-content a { color: var(--text-link); text-underline-offset: 2px; }
        .sakura-msg-content blockquote {
          border-left: 3px solid var(--accent-soft);
          padding-left: var(--space-3);
          color: var(--text-secondary);
          margin: var(--space-2) 0;
          font-style: italic;
        }
        .sakura-msg-content pre {
          background: var(--bg-tertiary);
          padding: var(--space-4);
          border-radius: var(--radius-md);
          overflow-x: auto;
          margin: var(--space-3) 0;
          font-size: var(--text-sm);
          line-height: 1.6;
        }
        .sakura-msg-content table {
          width: 100%;
          border-collapse: collapse;
          margin: var(--space-3) 0;
          font-size: var(--text-sm);
        }
        .sakura-msg-content th, .sakura-msg-content td {
          padding: var(--space-2) var(--space-3);
          border: 1px solid var(--border-subtle);
          text-align: left;
        }
        .sakura-msg-content th {
          background: var(--bg-muted);
          font-weight: 600;
        }
      `}</style>
    </motion.div>
  );
});

function MsgActionBtn({
  children,
  onClick,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: 26,
        height: 26,
        borderRadius: "var(--radius-sm)",
        border: "none",
        background: "transparent",
        color: "var(--text-tertiary)",
        cursor: "pointer",
        transition: "all var(--duration-fast) var(--ease-standard)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--bg-hover)";
        e.currentTarget.style.color = "var(--accent)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = "var(--text-tertiary)";
      }}
    >
      {children}
    </button>
  );
}
