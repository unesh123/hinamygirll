import { useEffect, useState, type CSSProperties } from "react";

export type OrbState = "idle" | "listening" | "thinking" | "speaking";

export interface GlowOrbProps {
  /** Voice/audio energy, 0..1. */
  level?: number;
  state?: OrbState;
  size?: number;
  label?: string;
}

function usePrefersReducedMotion(): boolean {
  const query = "(prefers-reduced-motion: reduce)";
  const [reduced, setReduced] = useState(() => window.matchMedia?.(query)?.matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq?.addEventListener) return;
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** Reactive "core" orb: pure CSS, driven by `level` and `state`. */
export function GlowOrb({ level = 0, state = "idle", size = 160, label }: GlowOrbProps) {
  const reduced = usePrefersReducedMotion();
  const clamped = Math.max(0, Math.min(1, Number.isFinite(level) ? level : 0));
  const style = { width: size, "--orb-level": reduced ? 0 : clamped } as CSSProperties;
  return (
    <div className="ds-orb" data-state={state} data-static={reduced} style={style} role="img" aria-label={label ?? `Core ${state}`}>
      <span className="ds-orb__halo" />
      <span className="ds-orb__ring ds-orb__ring--2" />
      <span className="ds-orb__ring" />
      <span className="ds-orb__core" />
    </div>
  );
}
