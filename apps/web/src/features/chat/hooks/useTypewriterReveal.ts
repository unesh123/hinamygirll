import { useEffect, useRef, useState } from "react";

/**
 * useTypewriterReveal — display-side token stream.
 *
 * Network deltas can land as chunks of any size; the interface should still
 * read like a mind speaking. This reveals the target string character-run by
 * character-run on rAF, auto-accelerating when far behind so long answers
 * never feel artificially slow, and snapping to the full text when done.
 */
export function useTypewriterReveal(target: string): string {
  const [shown, setShown] = useState(target);
  const targetRef = useRef(target);
  const shownLenRef = useRef(0);
  const rafRef = useRef(0);
  const activeRef = useRef(false);

  useEffect(() => {
    targetRef.current = target;
    if (typeof window === "undefined") return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (reduceMotion) {
      shownLenRef.current = target.length;
      setShown(target);
      return;
    }
    // Reset when a new turn starts (target shrank to empty or restarted).
    if (target.length < shownLenRef.current) shownLenRef.current = 0;
    if (activeRef.current) return;

    activeRef.current = true;
    const step = () => {
      const full = targetRef.current;
      const current = shownLenRef.current;
      if (current >= full.length) {
        if (shownLenRef.current !== full.length || full.length === 0) {
          shownLenRef.current = full.length;
          setShown(full);
        }
        // Caught up: park the loop. A longer target restarts it via the effect.
        activeRef.current = false;
        return;
      }
      const remaining = full.length - current;
      // Catch-up curve: smooth typing at short distances, bursts at long ones.
      const advance = Math.max(2, Math.min(46, Math.ceil(remaining / 10)));
      const next = Math.min(full.length, current + advance);
      shownLenRef.current = next;
      setShown(full.slice(0, next));
      rafRef.current = window.requestAnimationFrame(step);
    };
    rafRef.current = window.requestAnimationFrame(step);

    return () => {
      activeRef.current = false;
      window.cancelAnimationFrame(rafRef.current);
    };
  }, [target]);

  // Final safety: if the component unmounts mid-stream nothing leaks; when a
  // turn completes (target stable) the loop naturally holds at full length.
  return shown;
}
