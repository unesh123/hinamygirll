/**
 * MessageBubble — premium animated message with framer-motion.
 * Assistants get document-style spacious content; users get compact glass bubbles.
 * Streaming reveals words with subtle upward blur-to-clear animation.
 */

import { memo, useMemo } from "react";
import { motion } from "framer-motion";
import type { TranscriptMessage } from "../../companion/types";
import styles from "./MessageBubble.module.css";
import { GenericResultRenderer } from "./GenericResultRenderer";
import { ToolApprovalPanel } from "./ToolApprovalPanel";
import type { AssistantTurnPlan } from "../../../contracts/assistantTurnPlan";

interface Props {
  message: TranscriptMessage;
  companionName?: string;
  isStreaming?: boolean;
  isPartial?: boolean;
  isThinking?: boolean;
  isGroupStart?: boolean;
  "aria-label"?: string;
  "data-testid"?: string;
  onResolveTool?: (
    messageId: string,
    request: AssistantTurnPlan["toolRequests"][number],
    approved: boolean,
  ) => void | Promise<void>;
}

/** Simple markdown-to-HTML for inline formatting */
function renderMarkdown(text: string): string {
  let html = text
    // Bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Inline code
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // @ Power-up keywords
    .replace(/(^|\s)(@[a-zA-Z0-9_]+)/g, '$1<span style="color:#ffc8d8;font-weight:700;padding:2px 7px;background:rgba(238,145,173,.15);border-radius:6px;margin:0 2px;border:1px solid rgba(255,193,211,.24);">$2</span>')
    // Hashtags
    .replace(/(^|\s)(#[a-zA-Z0-9_]+)/g, '$1<span style="color:#f2c6d4;font-weight:650;padding:2px 6px;background:rgba(255,255,255,.06);border-radius:5px;margin:0 2px;">$2</span>');
  return html;
}

export const MessageBubble = memo(function MessageBubble({
  message,
  companionName = "HINAA",
  isStreaming = false,
  isPartial = false,
  isThinking = false,
  isGroupStart = true,
  "aria-label": ariaLabel,
  "data-testid": testId,
  onResolveTool,
}: Props) {
  const isUser = message.role === "user";
  const isError =
    message.text.startsWith("Response failed safely.") ||
    message.text.includes("rate limited");

  const formattedTime = useMemo(() => {
    try {
      return new Date(message.createdAt).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }, [message.createdAt]);

  const isLong = message.text.length > 120;
  const renderedHTML = useMemo(() => renderMarkdown(message.text), [message.text]);

  return (
    <motion.article
      className={[
        styles.bubble,
        isUser ? styles.user : styles.assistant,
        isGroupStart ? styles.groupStart : styles.grouped,
        isStreaming ? styles.streaming : "",
        isPartial ? styles.partial : "",
        isThinking ? styles.thinking : "",
        isError ? styles.error : "",
      ]
        .filter(Boolean)
        .join(" ")}
      data-role={message.role}
      data-group-start={isGroupStart ? "true" : "false"}
      data-testid={testId}
      aria-label={ariaLabel}
      initial={{ opacity: 0, y: 12, x: isUser ? 16 : -16 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 0.61, 0.36, 1] }}
      layout="position"
    >
      {/* HINAA identity chip */}
      {!isUser && isGroupStart && !isThinking && (
        <motion.span
          className={styles.chip}
          aria-hidden="true"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.08, duration: 0.35, ease: [0.34, 1.56, 0.64, 1] }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </motion.span>
      )}

      <div className={styles.stack}>
        {/* Thinking dots */}
        {isThinking ? (
          <div className={styles.thinkingDots} aria-live="polite">
            <motion.span className={styles.thinkingPulse} animate={{ opacity: [0.45, 1, 0.45] }} transition={{ duration: 1.25, repeat: Infinity }} />
            <span className={styles.thinkingLabel}>Preparing a focused response</span>
          </div>
        ) : (
          <div className={styles.content}>
            <div className={styles.text}>
              {isStreaming && message.text ? (
                <>
                  <span dangerouslySetInnerHTML={{ __html: renderedHTML }} />
                  <span className={styles.cursor} aria-hidden="true" />
                </>
              ) : isUser ? (
                message.text
              ) : (
                <span dangerouslySetInnerHTML={{ __html: renderedHTML }} />
              )}
            </div>
          </div>
        )}

        {message.role === "assistant" && message.plan && message.plan.toolRequests.length > 0 && onResolveTool ? (
          <ToolApprovalPanel messageId={message.id} requests={message.plan.toolRequests} activity={message.toolActivity} onResolve={onResolveTool} />
        ) : null}

        {/* Render tool results */}
        {message.toolResults && message.toolResults.length > 0 && (
          <div className={styles.toolResultsContainer} style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {message.toolResults.map((tr, i) => (
              <GenericResultRenderer key={`${tr.toolName}-${i}`} toolName={tr.toolName} result={tr.result} />
            ))}
          </div>
        )}

        {/* Footer */}
        {!isThinking && (
          <div className={styles.footer}>
            {isPartial ? (
              <span className={styles.partialLabel}>speaking…</span>
            ) : isStreaming ? (
              <span className={styles.partialLabel}>writing…</span>
            ) : (
              <time
                className={styles.time}
                dateTime={message.createdAt}
                title={new Date(message.createdAt).toLocaleString()}
              >
                {formattedTime}
              </time>
            )}
          </div>
        )}
      </div>
    </motion.article>
  );
});
