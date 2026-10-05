/**
 * useAutoScroll — buttery-smooth, non-intrusive auto-scroll for chat streams.
 *
 * Rules:
 * - When at the bottom and new tokens arrive, smoothly pin to bottom.
 * - When the user scrolls UP to read history, immediately release pin and NEVER yank them back.
 * - When the user scrolls back within margin of bottom, seamlessly re-engage pin.
 * - Batch all scroll updates with requestAnimationFrame to prevent layout thrashing and lag.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const PIN_THRESHOLD_PX = 72; // within this distance = engaged at bottom
const REPIN_THRESHOLD_PX = 36; // re-pin when user scrolls near the bottom

function getGapFromBottom(el: HTMLElement): number {
  return el.scrollHeight - el.scrollTop - el.clientHeight;
}

export function useAutoScroll(deps: unknown[]) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const [showJump, setShowJump] = useState(false);
  const pinnedRef = useRef(true);
  const isProgrammaticScrollRef = useRef(false);
  const rafIdRef = useRef<number>(0);

  const followToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el || !pinnedRef.current) return;
    if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    rafIdRef.current = requestAnimationFrame(() => {
      rafIdRef.current = 0;
      if (!pinnedRef.current || !el) return;
      const gap = getGapFromBottom(el);
      if (gap > 1) {
        isProgrammaticScrollRef.current = true;
        el.scrollTop = el.scrollHeight;
      }
    });
  }, []);

  const scrollToBottom = useCallback((smooth = true) => {
    const el = scrollRef.current;
    pinnedRef.current = true;
    setShowJump(false);
    if (!el) return;
    isProgrammaticScrollRef.current = true;
    if (smooth && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, []);

  // Monitor user gestures and scroll position with instantaneous gesture capture
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    // Capture wheel events immediately to release pin the moment user scrolls upward
    const handleWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) {
        // User is scrolling UP to read history — immediately disengage auto-pin
        pinnedRef.current = false;
        setShowJump(true);
      } else if (e.deltaY > 0) {
        const gap = getGapFromBottom(el);
        if (gap <= REPIN_THRESHOLD_PX) {
          pinnedRef.current = true;
          setShowJump(false);
        }
      }
    };

    // Capture touch swipes on mobile or touchscreens
    let touchStartY = 0;
    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        touchStartY = e.touches[0].clientY;
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        const delta = e.touches[0].clientY - touchStartY;
        if (delta > 8) {
          // Swiping down moves scroll UP — immediately release pin
          pinnedRef.current = false;
          setShowJump(true);
        } else if (delta < -8) {
          const gap = getGapFromBottom(el);
          if (gap <= REPIN_THRESHOLD_PX) {
            pinnedRef.current = true;
            setShowJump(false);
          }
        }
      }
    };

    const handleScroll = () => {
      if (isProgrammaticScrollRef.current) {
        isProgrammaticScrollRef.current = false;
        return;
      }
      const gap = getGapFromBottom(el);
      if (gap > PIN_THRESHOLD_PX) {
        if (pinnedRef.current) {
          pinnedRef.current = false;
          setShowJump(true);
        }
      } else if (gap <= REPIN_THRESHOLD_PX) {
        if (!pinnedRef.current) {
          pinnedRef.current = true;
          setShowJump(false);
        }
      }
    };

    el.addEventListener("wheel", handleWheel, { passive: true });
    el.addEventListener("touchstart", handleTouchStart, { passive: true });
    el.addEventListener("touchmove", handleTouchMove, { passive: true });
    el.addEventListener("scroll", handleScroll, { passive: true });

    return () => {
      el.removeEventListener("wheel", handleWheel);
      el.removeEventListener("touchstart", handleTouchStart);
      el.removeEventListener("touchmove", handleTouchMove);
      el.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // Follow height expansion for newly added child nodes (cards, images)
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || typeof MutationObserver === "undefined") return;

    let mutationRaf = 0;
    let lastMutationScroll = 0;
    const observer = new MutationObserver(() => {
      if (!pinnedRef.current) return;
      const now = performance.now();
      if (now - lastMutationScroll < 100) return; // Max 10 adjustments/sec
      if (mutationRaf) return;
      mutationRaf = requestAnimationFrame(() => {
        mutationRaf = 0;
        lastMutationScroll = performance.now();
        if (pinnedRef.current && el) {
          const gap = getGapFromBottom(el);
          if (gap > 1) {
            isProgrammaticScrollRef.current = true;
            el.scrollTop = el.scrollHeight;
          }
        }
      });
    });

    // Observe child additions without thrashing on individual character changes
    observer.observe(el, { childList: true });
    return () => {
      if (mutationRaf) cancelAnimationFrame(mutationRaf);
      observer.disconnect();
    };
  }, []);

  // Re-check whenever deps change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (pinnedRef.current) {
      followToBottom();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, []);

  return { scrollRef, endRef, showJump, scrollToBottom };
}
