/**
 * TranscriptView — cinematic animated message list with spatial document layout.
 * Welcome state: animated "Hello, Unesh" with capability cards.
 */

import { Fragment, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Lenis from "lenis";
import gsap from "gsap";
import { GeneratingLoader } from "../../../components/ui/GeneratingLoader";
import { useAutoScroll } from "../hooks/useAutoScroll";
import type { TranscriptMessage } from "../../companion/types";
import { MessageBubble } from "./MessageBubble";
import { WelcomeScene } from "../../../components/ui/WelcomeScene";
import type { AssistantTurnPlan } from "../../../contracts/assistantTurnPlan";

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
  onResolveTool?: (
    messageId: string,
    request: AssistantTurnPlan["toolRequests"][number],
    approved: boolean,
  ) => void | Promise<void>;
  /** Autonomy mode — actions run without a per-action approval click. */
  autoRunTools?: boolean;
}

export function TranscriptView({
  messages,
  streamingText,
  partialTranscript,
  companionName,
  isThinking,
  onWelcomeAction,
  onResolveTool,
  autoRunTools = false,
}: Props) {
  const { scrollRef, endRef, showJump, scrollToBottom } = useAutoScroll([
    messages.length,
    streamingText,
    partialTranscript,
    isThinking,
  ]);
  const contentRef = useRef<HTMLDivElement>(null);
  const bgRef = useRef<HTMLDivElement>(null);

  // Lenis & GSAP setup
  useEffect(() => {
    if (!scrollRef.current || !contentRef.current) return;

    // Check for reduced motion or coarse pointer (touch)
    const isTouch = window.matchMedia("(pointer: coarse)").matches;
    const isReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    
    if (isTouch || isReducedMotion) return; // Skip Lenis on touch or reduced motion

    const lenis = new Lenis({
      wrapper: scrollRef.current,
      content: contentRef.current,
      lerp: 0.1,
      duration: 1.2,
      smoothWheel: true,
      wheelMultiplier: 1.2,
    });

    const onScroll = (e: any) => {
      // Ambient scroll-linked GSAP effect (Ink Rose atmosphere)
      if (bgRef.current) {
        gsap.to(bgRef.current, {
          y: e.scroll * 0.15,
          opacity: Math.max(0.2, 0.4 - e.scroll * 0.0005),
          duration: 0, // scrub directly
        });
      }
    };

    lenis.on('scroll', onScroll);

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    const rafId = requestAnimationFrame(raf);

    return () => {
      lenis.destroy();
      cancelAnimationFrame(rafId);
    };
  }, [scrollRef]);

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
        <WelcomeScene onAction={onWelcomeAction} />
      </motion.div>
    );
  }

  /* ── Conversation view ────────────────────────────────────── */
  return (
    <div className={styles.container} ref={scrollRef} style={{ position: 'relative' }}>
      {/* GSAP Ambient Background */}
      <div 
        ref={bgRef} 
        style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, height: '150%',
          background: 'radial-gradient(ellipse at top center, rgba(238,145,173,0.1) 0%, transparent 70%)',
          pointerEvents: 'none',
          zIndex: 0,
        }} 
      />
      
      <div ref={contentRef} style={{ position: 'relative', zIndex: 1, paddingBottom: 40, display: 'flex', flexDirection: 'column' }}>
      {messages.map((msg, i) => {
        const prev = messages[i - 1];
        const showDivider =
          Boolean(prev?.createdAt) &&
          gapSeconds(prev.createdAt, msg.createdAt) > TURN_GAP_SECONDS;

        const isGroupStart =
          i === 0 ||
          msg.role !== messages[i - 1]?.role ||
          showDivider;

        return (
          <Fragment key={msg.id || `msg-${i}`}>
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
              onResolveTool={onResolveTool}
              autoRunTools={autoRunTools}
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
            onClick={() => scrollToBottom()}
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
    </div>
  );
}
