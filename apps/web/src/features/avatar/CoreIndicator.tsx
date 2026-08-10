/**
 * CoreIndicator — HINAA's crystalline core, rendered just below her face at
 * the collarbone. It is not decoration: it shows her actual state through
 * color (cyan listening / violet reasoning / blue speaking / white idle /
 * amber attention / red failure) and a subtle iris ring that brightens when
 * she enters deep reasoning or recalls something important.
 */
import { useMemo } from "react";
import type { CSSProperties } from "react";
import {
  CORE_STATE_META,
  coreStateFor,
  irisRingActiveFor,
  type CoreState,
} from "./coreState";

interface CoreIndicatorProps {
  state: string;
  /** Override label (e.g. "Confirm" instead of "Attention"). */
  label?: string;
  compact?: boolean;
}

export function CoreIndicator({ state, label, compact }: CoreIndicatorProps) {
  const core: CoreState = useMemo(() => coreStateFor(state), [state]);
  const meta = CORE_STATE_META[core];
  const irisBright = irisRingActiveFor(state);

  return (
    <div
      className={`core-indicator${compact ? " core-indicator-compact" : ""}`}
      data-core={core}
      data-iris-ring={irisBright ? "bright" : "quiet"}
      role="status"
      aria-label={`${label ?? meta.label} — ${meta.detail}`}
      title={meta.detail}
    >
      <span className="core-aura" aria-hidden="true" />
      <span className="core-iris-ring" aria-hidden="true" />
      <span
        className="core-crystal"
        aria-hidden="true"
        style={{ "--core-color": meta.color } as CSSProperties}
      />
      <span className="core-crystal-shine" aria-hidden="true" />
      <span className="core-label">{label ?? meta.label}</span>
    </div>
  );
}
