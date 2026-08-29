import { memo } from "react";
import { motion } from "framer-motion";
import { Copy, Check, RotateCcw, ExternalLink } from "lucide-react";
import { useState, useCallback } from "react";

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

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(message.text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [message.text]);

  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
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
          {renderMarkdownContent(message.text)}
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

/**
 * Basic markdown-like rendering. In production, use a proper markdown renderer.
 * This handles the most common cases for HINAA's response format.
 */
function renderMarkdownContent(text: string): React.ReactNode {
  // Split by double newlines for paragraphs
  const blocks = text.split(/\n\n+/);
  return blocks.map((block, i) => {
    const trimmed = block.trim();
    if (!trimmed) return null;

    // Heading
    if (trimmed.startsWith("### ")) return <h3 key={i}>{trimmed.slice(4)}</h3>;
    if (trimmed.startsWith("## ")) return <h2 key={i}>{trimmed.slice(3)}</h2>;
    if (trimmed.startsWith("# ")) return <h1 key={i}>{trimmed.slice(2)}</h1>;

    // Code block
    if (trimmed.startsWith("```")) {
      const lines = trimmed.split("\n");
      const lang = lines[0].replace("```", "").trim();
      const code = lines.slice(1, -1).join("\n");
      return (
        <pre key={i}>
          {lang && <div style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginBottom: "var(--space-2)" }}>{lang}</div>}
          <code>{code}</code>
        </pre>
      );
    }

    // Table
    if (trimmed.includes("|") && trimmed.includes("---")) {
      const rows = trimmed.split("\n").filter((r) => !r.match(/^\|[\s-|]+\|$/));
      if (rows.length > 0) {
        const headerCells = rows[0].split("|").filter(Boolean).map((c) => c.trim());
        const dataRows = rows.slice(1).map((r) => r.split("|").filter(Boolean).map((c) => c.trim()));
        return (
          <table key={i}>
            <thead>
              <tr>{headerCells.map((cell, j) => <th key={j}>{cell}</th>)}</tr>
            </thead>
            <tbody>
              {dataRows.map((cells, j) => (
                <tr key={j}>{cells.map((cell, k) => <td key={k}>{cell}</td>)}</tr>
              ))}
            </tbody>
          </table>
        );
      }
    }

    // Blockquote
    if (trimmed.startsWith("> ")) {
      return <blockquote key={i}>{trimmed.slice(2)}</blockquote>;
    }

    // List
    if (trimmed.match(/^[-*]\s/m)) {
      const items = trimmed.split("\n").map((l) => l.replace(/^[-*]\s/, "").trim());
      return <ul key={i}>{items.map((item, j) => <li key={j}>{item}</li>)}</ul>;
    }
    if (trimmed.match(/^\d+\.\s/m)) {
      const items = trimmed.split("\n").map((l) => l.replace(/^\d+\.\s/, "").trim());
      return <ol key={i}>{items.map((item, j) => <li key={j}>{item}</li>)}</ol>;
    }

    // Regular paragraph with inline formatting
    return <p key={i}>{renderInlineFormatting(trimmed)}</p>;
  });
}

function renderInlineFormatting(text: string): React.ReactNode {
  // Bold
  const parts: React.ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*|`(.+?)`|\[(.+?)\]\((.+?)\)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[1]) {
      parts.push(<strong key={match.index} style={{ fontWeight: 600 }}>{match[1]}</strong>);
    } else if (match[2]) {
      parts.push(<code key={match.index} style={{
        background: "var(--bg-muted)",
        padding: "1px 5px",
        borderRadius: "var(--radius-xs)",
        fontSize: "0.875em",
        color: "var(--accent-hover)",
      }}>{match[2]}</code>);
    } else if (match[3] && match[4]) {
      parts.push(
        <a key={match.index} href={match[4]} target="_blank" rel="noopener noreferrer">
          {match[3]} <ExternalLink size={11} style={{ verticalAlign: -1 }} />
        </a>
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}
