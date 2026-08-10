/**
 * Composer — autoresizing textarea-based message input.
 *
 * Features:
 * - Autoresizes with content (1–6 rows)
 * - Enter sends, Shift+Enter inserts newline
 * - Disabled while assistant is generating
 * - Accessible label and send button
 * - Animated send button with loading spinner during streaming
 */

import { useCallback, useEffect, useRef } from "react";
import styles from "./Composer.module.css";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  placeholder?: string;
  disabled?: boolean;
  isGenerating?: boolean;
  companionName?: string;
}

export function Composer({
  value,
  onChange,
  onSend,
  placeholder,
  disabled = false,
  isGenerating = false,
  companionName = "Hinaa",
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Autoresize: adjust height after every value change.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const lineH = parseInt(getComputedStyle(el).lineHeight || "20", 10);
    const maxH = lineH * 6 + 24; // max 6 rows + padding
    el.style.height = `${Math.min(el.scrollHeight, maxH)}px`;
  }, [value]);

  const handleKey = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (value.trim() && !disabled && !isGenerating) {
          onSend();
        }
      }
    },
    [value, disabled, isGenerating, onSend],
  );

  const canSend = value.trim().length > 0 && !disabled && !isGenerating;

  return (
    <form
      className={styles.composer}
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSend();
      }}
      aria-label="Message composer"
    >
      <label htmlFor="chat-composer" className="sr-only">
        Type a message
      </label>
      <textarea
        id="chat-composer"
        ref={textareaRef}
        className={styles.textarea}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKey}
        placeholder={
          placeholder ?? `Message ${companionName}… (Shift+Enter for newline)`
        }
        disabled={disabled}
        rows={1}
        aria-label="Type a message"
        aria-multiline="true"
        aria-disabled={disabled}
        autoComplete="off"
        spellCheck
      />

      <button
        type="submit"
        className={`${styles.sendBtn} ${canSend ? styles.active : ""}`}
        aria-label={isGenerating ? "Generating response…" : "Send message"}
        disabled={!canSend}
      >
        {isGenerating ? (
          <span className={styles.spinner} aria-hidden="true" />
        ) : (
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="none"
            width="18"
            height="18"
          >
            <path
              d="M3 10L17 3L10 17L8.5 11.5L3 10Z"
              fill="currentColor"
              stroke="currentColor"
              strokeWidth="0.5"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>
    </form>
  );
}
