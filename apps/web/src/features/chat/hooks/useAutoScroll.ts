/**
 * useAutoScroll — smart auto-scroll for conversation transcripts.
 *
 * Rules:
 * - Auto-scroll to bottom only when user is already at/near the bottom.
 * - Never force-scroll a user who has scrolled up to read older messages.
 * - Show a "jump to latest" indicator when the user is not at bottom.
 * - Expose a manual scrollToBottom function for the jump button.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const SCROLL_THRESHOLD_PX = 80; // within this many px of bottom = "at bottom"

export function useAutoScroll(deps: unknown[]) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const [showJump, setShowJump] = useState(false);

  const isAtBottom = useCallback((): boolean => {
    const el = scrollRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_THRESHOLD_PX;
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    endRef.current?.scrollIntoView({ behavior, block: "end" });
    setShowJump(false);
  }, []);

  // Track user scroll to detect whether they've scrolled up.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handleScroll = () => {
      setShowJump(!isAtBottom());
    };
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [isAtBottom]);

  // Auto-scroll only when user is at the bottom.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (isAtBottom()) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    } else {
      // User is reading — just show the jump indicator.
      setShowJump(true);
    }
  // Re-run whenever the conversation content changes.
  // deps is passed in from the caller to keep this hook generic.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { scrollRef, endRef, showJump, scrollToBottom };
}
