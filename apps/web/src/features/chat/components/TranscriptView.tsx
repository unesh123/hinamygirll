/**
 * TranscriptView — cinematic animated message list with spatial document layout.
 * Welcome state: animated "Hello, Unesh" with capability cards.
 */

import { Fragment } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { GeneratingLoader } from "../../../components/ui/GeneratingLoader";
import { useAutoScroll } from "../hooks/useAutoScroll";
import type { TranscriptMessage } from "../../companion/types";
import { MessageBubble } from "./MessageBubble";
import { WelcomeScene } from "../../../components/ui/WelcomeScene";

import styles from "./TranscriptView.module.css";

const TURN_GAP_SECONDS = 90;

function gapSeconds(a: string, b: string): number {
  const ta = Date.parse(a);
  const tb = Date.parse(b);
  if (Number.isNaN(ta) || Number.isNaN(tb)) return 0;
  return Math.max(0, (tb - ta) / 1000);
}

function dividerTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

interface Props {
  messages: TranscriptMessage[];
  streamingText: string;
  partialTranscript: string;
  companionName: string;
  isThinking: boolean;
  onWelcomeAction?: (action: string) => void;
}

export function TranscriptView({
  messages,
  streamingText,
  partialTranscript,
  companionName,
  isThinking,
  onWelcomeAction,
}: Props) {
  const { scrollRef, endRef, showJump, scrollToBottom } = useAutoScroll([
    messages.length,
    streamingText,
    partialTranscript,
    isThinking,
  ]);

  const isEmpty =
    messages.length === 0 &&
    !streamingText &&
    !partialTranscript &&
    !isThinking;

  /* ── Cinematic empty state ────────────────────────────────── */
  if (isEmpty) {
    return (
      <motion.div
        className={styles.empty}
        aria-label="No messages yet"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
      >
        <WelcomeScene userName="Unesh" onAction={onWelcomeAction} />
      </motion.div>
    );
  }

  /* ── Conversation view ────────────────────────────────────── */
  const isPreviousUser = (i: number) =>
    i > 0 && messages[i - 1]?.role === "user";

  return (
    <div className={styles.container} ref={scrollRef}>
      {messages.map((msg, i) => {
        const prev = messages[i - 1];
        const showDivider =
          prev?.createdAt &&
          gapSeconds(prev.createdAt, msg.createdAt) > TURN_GAP_SECONDS;

        const isGroupStart =
          i === 0 ||
          msg.role !== messages[i - 1]?.role ||
          showDivider;

        return (
          <Fragment key={msg.id ?? i}>
            {showDivider && (
              <div className={styles.divider} role="separator">
                <time>{dividerTime(msg.createdAt)}</time>
              </div>
            )}
            <MessageBubble
              message={msg}
              companionName={companionName}
              isGroupStart={isGroupStart}
              isStreaming={false}
              isPartial={false}
              isThinking={false}
              aria-label={`${msg.role === "user" ? "You" : companionName}: ${msg.text.slice(0, 60)}`}
              data-testid={`msg-${i}`}
            />
          </Fragment>
        );
      })}

      {/* Partial transcript (voice) */}
      {partialTranscript && (
        <MessageBubble
          message={{
            id: "partial",
            role: "user",
            text: partialTranscript,
            createdAt: new Date().toISOString(),
          }}
          companionName={companionName}
          isPartial
          isGroupStart
          aria-label={`Speaking: ${partialTranscript.slice(0, 60)}`}
        />
      )}

      {/* Streaming assistant response */}
      {streamingText && (
        <MessageBubble
          message={{
            id: "streaming",
            role: "assistant",
            text: streamingText,
            createdAt: new Date().toISOString(),
          }}
          companionName={companionName}
          isStreaming
          isGroupStart
          aria-label="HINAA is responding"
        />
      )}

      {/* Thinking indicator */}
      {isThinking && (
        <MessageBubble
          message={{
            id: "thinking",
            role: "assistant",
            text: "",
            createdAt: new Date().toISOString(),
          }}
          companionName={companionName}
          isThinking
          isGroupStart
          aria-label="HINAA is thinking"
        />
      )}

      {/* Jump to bottom */}
      <AnimatePresence>
        {showJump && (
          <motion.button
            className={styles.jumpBtn}
            onClick={scrollToBottom}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            aria-label="Scroll to latest message"
          >
            ↓ Latest
          </motion.button>
        )}
      </AnimatePresence>

      {/* Invisible scroll anchor */}
      <div ref={endRef} />
    </div>
  );
}
