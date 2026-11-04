import React from "react";
import { Sparkles, Activity, ShieldCheck } from "lucide-react";
import { useStatus, type SystemStatus } from "../hooks/useStatus";

export interface StatProps {
  label: string;
  value: string | number;
  highlight?: boolean;
}

export function Stat({ label, value, highlight = false }: StatProps) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="text-[10px] font-bold tracking-wider text-text-muted uppercase">
        {label}
      </span>
      <span
        className={`font-semibold tabular-nums ${
          highlight ? "text-accent" : "text-text-primary"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export interface StatusBarProps {
  statusOverride?: SystemStatus;
  messageCount?: number;
  onOpenSettings?: () => void;
  activeModelName?: string;
}

export function StatusBar({
  statusOverride,
  messageCount,
  onOpenSettings,
  activeModelName = "HINAA-v2.0",
}: StatusBarProps) {
  const liveStatus = useStatus(messageCount);
  const status = statusOverride ?? liveStatus;

  return (
    <header className="col-span-full h-12 flex items-center justify-between px-4 bg-frost/80 backdrop-blur-md border border-glass-border rounded-xl shadow-soft min-w-0">
      {/* ── Left Cluster: Brand & Model Identifier ── */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-accent to-brand-300 flex items-center justify-center text-white shadow-xs flex-shrink-0">
            <Sparkles size={13} />
          </div>
          <span className="font-bold text-sm tracking-tight text-text-primary">
            HINAA <span className="text-accent text-xs font-semibold">OS</span>
          </span>
        </div>

        <div className="h-4 w-[1px] bg-glass-border-strong mx-1 flex-shrink-0" />

        <div className="flex items-center gap-1.5 text-xs text-text-secondary truncate min-w-0">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" />
          <span className="font-mono text-[11px] font-medium truncate">
            {activeModelName}
          </span>
        </div>
      </div>

      {/* ── Right Cluster: Live Telemetry Metrics (flex gap-6 tabular-nums) ── */}
      <div className="flex items-center gap-6 tabular-nums flex-shrink-0">
        <Stat label="TRACK" value={`${status.trackMs} ms`} />
        <Stat label="CTX" value={`${status.ctxPct}%`} />
        <Stat label="RENDER" value={`${status.renderFps} fps`} />
        <Stat label="MSGS" value={status.msgCount} highlight />

        {onOpenSettings && (
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex items-center gap-1 text-xs font-medium text-text-secondary hover:text-accent transition-colors py-1 px-2 rounded-md hover:bg-frost-light"
          >
            <ShieldCheck size={13} />
            <span>Config</span>
          </button>
        )}
      </div>
    </header>
  );
}
