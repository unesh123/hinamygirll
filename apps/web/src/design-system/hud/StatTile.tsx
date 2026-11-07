import type { ReactNode } from "react";
import { Panel } from "./Panel";

export interface StatTileProps {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
}

export function StatTile({ label, value, unit, hint }: StatTileProps) {
  return (
    <Panel className="ds-stat" brackets>
      <div className="ds-stat__label">{label}</div>
      <div className="ds-stat__value">
        {value}
        {unit && <span className="ds-stat__unit">{unit}</span>}
      </div>
      {hint && <div className="ds-stat__hint">{hint}</div>}
    </Panel>
  );
}
