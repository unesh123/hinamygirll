/**
 * useAutoScroll — smart auto-scroll for conversation transcripts.
 *
 * Rules:
 * - Follow the thread while the user is riding the bottom.
 * - Only a real input gesture may release that follow.
 * - Show a "jump to latest" control when the user is not at the bottom.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const SCROLL_THRESHOLD_PX = 80; // within this many px of bottom = "at bottom"

function gapFromBottom(el: HTMLElement): number {
  return el.scrollHeight - el.scrollTop - el.clientHeight;
}

export function useAutoScroll(deps: unknown[]) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const [showJump, setShowJump] = useState(false);
  /** Whether the user is riding the bottom of the thread. */
  const pinnedRef = useRef(true);
  /** Set by wheel/touch/key only — content growth and our own jumps never touch it. */
  const userScrolledRef = useRef(false);

  const isAtBottom = useCallback((): boolean => {
    const el = scrollRef.current;
    if (!el) return true;
    // A phone transcript is short, so a fixed 80px margin let one new bubble
    // read as "scrolled away" and the thread outran its own follow logic.
    return gapFromBottom(el) <= Math.max(SCROLL_THRESHOLD_PX, el.clientHeight * 0.5);
  }, []);

  const followToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current;
    userScrolledRef.current = false;
    pinnedRef.current = true;
    setShowJump(false);
    // Instant on purpose: an animated jump that gets interrupted, or that lands
    // while the thread is still growing, leaves the newest message out of view.
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  // Only an input gesture decides whether the user is reading history. A
  // programmatic jump briefly reports a large gap while the thread keeps
  // growing, and treating that as "scrolled away" silently killed the follow.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const markGesture = () => {
      userScrolledRef.current = true;
    };
    const handleScroll = () => {
      if (!userScrolledRef.current) return;
      const atBottom = isAtBottom();
      pinnedRef.current = atBottom;
      setShowJump(!atBottom);
    };
    el.addEventListener("wheel", markGesture, { passive: true });
    el.addEventListener("touchmove", markGesture, { passive: true });
    el.addEventListener("keydown", markGesture);
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      el.removeEventListener("wheel", markGesture);
      el.removeEventListener("touchmove", markGesture);
      el.removeEventListener("keydown", markGesture);
      el.removeEventListener("scroll", handleScroll);
    };
  }, [isAtBottom]);

  // Follow whatever changes the thread's height — streamed text, a progress
  // card, an image landing late — instead of trusting the caller to enumerate
  // every source of growth in its dependency list.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || typeof MutationObserver === "undefined") return;
    let frame = 0;
    const observer = new MutationObserver(() => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (pinnedRef.current) followToBottom();
      });
    });
    observer.observe(el, { childList: true, subtree: true, characterData: true });
    return () => {
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [followToBottom]);

  // Re-run whenever the conversation content changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (pinnedRef.current) followToBottom();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { scrollRef, endRef, showJump, scrollToBottom };
}
