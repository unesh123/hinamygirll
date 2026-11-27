import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Coalesces rapid token deltas per animation frame (~60fps) to avoid
 * synchronous React re-render storms while preserving instant final flush.
 */
export function useTokenBuffer() {
  const [text, setText] = useState("");
  const pendingRef = useRef("");
  const committedRef = useRef("");
  const rafRef = useRef<number | null>(null);

  const flush = useCallback(() => {
    if (rafRef.current !== null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (!pendingRef.current) return;
    committedRef.current += pendingRef.current;
    pendingRef.current = "";
    setText(committedRef.current);
  }, []);

  const push = useCallback(
    (delta: string) => {
      if (!delta) return;
      pendingRef.current += delta;
      if (typeof requestAnimationFrame !== "function") {
        flush();
        return;
      }
      if (rafRef.current === null) {
        rafRef.current = requestAnimationFrame(() => {
          rafRef.current = null;
          flush();
        });
      }
    },
    [flush],
  );

  const reset = useCallback((initial = "") => {
    if (rafRef.current !== null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    pendingRef.current = "";
    committedRef.current = initial;
    setText(initial);
  }, []);

  useEffect(() => {
    return () => {
      if (rafRef.current !== null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  return { text, push, flush, reset };
}
