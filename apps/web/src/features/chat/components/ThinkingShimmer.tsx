import { useEffect, useState } from "react";

export interface ThinkingShimmerProps {
  /** Active thinking/execution indicator. */
  active: boolean;
  /** Human-readable current stage, e.g. "routing intent", "calling tools". */
  stage?: string;
  /** Called once after `escalateAfterMs` of continuous thinking (prefetch, tone). */
  onEscalate?: () => void;
  escalateAfterMs?: number;
}

const SHIMMER_FRAMES = ["·", "·", "·"];

/**
 * Thinking Shimmer — the lightweight "Hina is working" signal used between the
 * user's send and the first streamed token. Renders a shimmering text band
 * with an animated gradient sweep; avoids any layout shift by reserving a
 * single line. Escalation lets the host layer upgrade the indicator (e.g. to
 * the full AgentActivityCard) if the wait gets long.
 */
export function ThinkingShimmer({
  active,
  stage = "Hina is thinking",
  onEscalate,
  escalateAfterMs = 4200,
}: ThinkingShimmerProps) {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    if (!active) return;
    const interval = setInterval(() => setFrame((f) => (f + 1) % SHIMMER_FRAMES.length), 180);
    return () => clearInterval(interval);
  }, [active]);

  useEffect(() => {
    if (!active || !onEscalate) return;
    const timer = setTimeout(onEscalate, escalateAfterMs);
    return () => clearTimeout(timer);
  }, [active, onEscalate, escalateAfterMs]);

  if (!active) return null;

  return (
    <div
      data-testid="thinking-shimmer"
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 px-1 py-1 text-xs italic text-text-muted"
    >
      <span
        aria-hidden
        className="inline-block h-3 w-3 rounded-full bg-accent/70 animate-pulse"
      />
      <span className="thinking-shimmer-text">{stage}</span>
      <span aria-hidden className="tracking-widest">
        {SHIMMER_FRAMES[frame]}
      </span>
    </div>
  );
}
