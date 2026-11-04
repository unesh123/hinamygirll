import React from "react";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ExternalLink,
  Camera,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

export interface BrowserActionItem {
  action_id: string;
  action_type: string;
  status: "SUCCESS" | "FAILED" | "APPROVAL_REQUIRED" | "CANCELLED" | "TIMEOUT";
  observed_url?: string;
  observed_title?: string;
  elapsed_ms: number;
  postcondition_verified?: boolean;
  postcondition_details?: string;
  failure_message?: string;
  screenshot_path?: string;
  timestamp: string;
}

export interface BrowserActionTimelineProps {
  actions: BrowserActionItem[];
}

export function BrowserActionTimeline({ actions }: BrowserActionTimelineProps) {
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  if (!actions || actions.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-text-muted italic border border-dashed border-glass-border rounded-xl">
        No actions recorded yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 font-sans text-xs">
      {actions.map((act, idx) => {
        const isExpanded = expandedId === act.action_id;
        const isSuccess = act.status === "SUCCESS";
        const isApproval = act.status === "APPROVAL_REQUIRED";
        const isFailed = act.status === "FAILED" || act.status === "TIMEOUT";

        const badgeClass = isSuccess
          ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
          : isApproval
          ? "bg-amber-500/10 text-amber-600 border-amber-500/20 animate-pulse"
          : isFailed
          ? "bg-rose-500/10 text-rose-600 border-rose-500/20"
          : "bg-slate-500/10 text-slate-600 border-slate-500/20";

        const StatusIcon = isSuccess
          ? CheckCircle2
          : isApproval
          ? AlertTriangle
          : isFailed
          ? XCircle
          : Clock;

        return (
          <div
            key={act.action_id || idx}
            className="p-2.5 rounded-lg bg-surface/60 border border-glass-border/70 hover:border-brand-300/40 transition-all flex flex-col gap-1.5"
          >
            {/* ── Top Row: Action type, Status, Elapsed ms ── */}
            <div className="flex items-center justify-between gap-2 min-w-0">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="w-4 h-4 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[10px] flex-shrink-0 font-bold">
                  {idx + 1}
                </span>
                <span className="font-mono text-[11px] font-semibold text-text-primary truncate">
                  {act.action_type}
                </span>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <span
                  className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border text-[10px] font-semibold tracking-wide ${badgeClass}`}
                >
                  <StatusIcon size={11} />
                  {act.status}
                </span>
                <span className="text-text-muted text-[10px] font-mono tabular-nums">
                  {act.elapsed_ms.toFixed(0)} ms
                </span>
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : act.action_id)}
                  className="text-text-muted hover:text-text-primary p-0.5"
                  aria-label={isExpanded ? "Collapse action details" : "Expand action details"}
                >
                  {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              </div>
            </div>

            {/* ── Observed URL & Title ── */}
            {act.observed_url && (
              <div className="flex items-center gap-1 text-[10px] text-text-secondary truncate">
                <span className="text-text-muted">URL:</span>
                <span className="truncate font-mono">{act.observed_url}</span>
                {act.observed_title && (
                  <span className="text-text-muted truncate">({act.observed_title})</span>
                )}
              </div>
            )}

            {/* ── Expandable Details: Postcondition / Errors ── */}
            {isExpanded && (
              <div className="mt-1 pt-1.5 border-t border-glass-border flex flex-col gap-1 text-[10px]">
                {act.postcondition_details && (
                  <div className="flex items-start gap-1">
                    <span className="text-text-muted font-medium">Postcondition:</span>
                    <span
                      className={
                        act.postcondition_verified ? "text-emerald-600 font-mono" : "text-rose-600 font-mono"
                      }
                    >
                      {act.postcondition_details}
                    </span>
                  </div>
                )}

                {act.failure_message && (
                  <div className="p-1.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-600">
                    <span className="font-semibold">Error:</span> {act.failure_message}
                  </div>
                )}

                {act.screenshot_path && (
                  <div className="flex items-center gap-1 text-accent hover:underline cursor-pointer">
                    <Camera size={11} />
                    <span>View Captured Screenshot ({act.screenshot_path.split(/[\\/]/).pop()})</span>
                  </div>
                )}

                <div className="text-[9px] text-text-muted">
                  Recorded at: {new Date(act.timestamp).toLocaleTimeString()}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
