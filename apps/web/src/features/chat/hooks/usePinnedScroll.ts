import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

export interface UsePinnedScrollOptions {
  scrollRef: RefObject<HTMLElement | null>;
  itemCount: number;
  streamingKey?: string | number;
  thresholdPx?: number;
}

export function usePinnedScroll({
  scrollRef,
  itemCount,
  streamingKey,
  thresholdPx = 48,
}: UsePinnedScrollOptions) {
  const [pinned, setPinned] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const prevCountRef = useRef(itemCount);
  const pinnedRef = useRef(true);
  pinnedRef.current = pinned;

  const isNearBottom = useCallback(
    (el: HTMLElement) => el.scrollHeight - el.scrollTop - el.clientHeight <= thresholdPx,
    [thresholdPx],
  );

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "auto") => {
    const el = scrollRef.current;
    if (!el) return;
    setPinned(true);
    setUnreadCount(0);
    if (typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior });
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [scrollRef]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = isNearBottom(el);
    setPinned(nearBottom);
    if (nearBottom) {
      setUnreadCount(0);
    }
  }, [isNearBottom, scrollRef]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [scrollRef, handleScroll]);

  useEffect(() => {
    const delta = Math.max(0, itemCount - prevCountRef.current);
    prevCountRef.current = itemCount;
    if (pinnedRef.current) {
      scrollToBottom("auto");
    } else if (delta > 0) {
      setUnreadCount((c) => c + delta);
    }
  }, [itemCount, scrollToBottom]);

  useEffect(() => {
    if (pinnedRef.current && streamingKey) {
      scrollToBottom("auto");
    }
  }, [streamingKey, scrollToBottom]);

  return {
    pinned,
    unreadCount,
    scrollToBottom,
    onScroll: handleScroll,
  };
}
