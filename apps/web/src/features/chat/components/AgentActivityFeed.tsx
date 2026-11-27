import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  ShieldAlert,
  Sparkles,
  Check,
  X,
} from "lucide-react";
import { ActivityFeedV2 } from "./ActivityFeedV2";
import type { ActivityStep } from "./AgentActivityCard";
import type { PendingToolApproval, RichActivityStep, TurnArtifact } from "../contracts/agentEvents";

export interface AgentActivityFeedProps {
  steps: Array<ActivityStep | RichActivityStep>;
  thought?: string;
  thoughtSummary?: string | null;
  artifacts?: TurnArtifact[];
  pendingApproval?: PendingToolApproval | null;
  onApprove?: (approval: PendingToolApproval) => void;
  onReject?: (approval: PendingToolApproval) => void;
  variant?: "rail" | "inline";
  isActive?: boolean;
}

export function AgentActivityFeed({
  steps,
  thought,
  thoughtSummary,
  artifacts = [],
  pendingApproval = null,
  onApprove,
  onReject,
  variant = "inline",
  isActive = false,
}: AgentActivityFeedProps) {
  const [thoughtExpanded, setThoughtExpanded] = useState(false);

  const hasContent =
    steps.length > 0 ||
    Boolean(thought?.trim()) ||
    artifacts.length > 0 ||
    pendingApproval !== null ||
    isActive;

  if (!hasContent) return null;

  const parallelCount = new Set(
    steps
      .map((s) => (s as RichActivityStep).parallelGroup)
      .filter((g): g is string => Boolean(g)),
  ).size;

  return (
    <aside
      data-testid="agent-activity-feed"
      aria-label="Live execution activity"
      className={
        variant === "rail"
          ? "w-[320px] shrink-0 h-full overflow-y-auto border-l p-3 flex flex-col gap-3"
          : "w-full rounded-[var(--radius-card)] border p-3 flex flex-col gap-2.5"
      }
      style={{
        background: variant === "rail" ? "var(--chat-rail-bg)" : "var(--bg-elevated)",
        borderColor: "var(--border-subtle)",
        color: "var(--text-primary)",
      }}
    >
      <header className="flex items-center justify-between gap-2 text-xs">
        <span className="font-semibold tracking-tight flex items-center gap-1.5">
          <Sparkles size={13} style={{ color: "var(--accent-primary)" }} />
          Execution Activity
        </span>
        <div className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
          {parallelCount > 0 && (
            <span
              className="px-1.5 py-0.5 rounded-[var(--radius-pill)] border text-[10px] font-medium"
              style={{ borderColor: "var(--border-subtle)" }}
            >
              {parallelCount} parallel batch{parallelCount > 1 ? "es" : ""}
            </span>
          )}
          <span>{steps.length} step{steps.length === 1 ? "" : "s"}</span>
        </div>
      </header>

      {thought && thought.trim() && (
        <div
          className="rounded-xl border px-2.5 py-2 text-xs"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--bg-glass)",
          }}
        >
          <button
            type="button"
            onClick={() => setThoughtExpanded((v) => !v)}
            aria-expanded={thoughtExpanded}
            className="w-full flex items-center gap-1.5 text-left font-medium cursor-pointer"
            style={{ color: "var(--text-secondary)" }}
          >
            {thoughtExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            <span className="truncate">
              {thoughtSummary || "Planner reasoning notes"}
            </span>
          </button>
          {thoughtExpanded && (
            <pre
              className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-relaxed"
              style={{
                color: "var(--text-muted)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {thought}
            </pre>
          )}
        </div>
      )}

      {pendingApproval && (
        <div
          data-testid="inline-approval-banner"
          role="alert"
          className="rounded-xl border p-2.5 text-xs flex flex-col gap-2"
          style={{
            borderColor: "var(--status-warn)",
            background: "var(--bg-elevated)",
          }}
        >
          <div className="flex items-start gap-2">
            <ShieldAlert size={15} style={{ color: "var(--status-warn)" }} className="shrink-0 mt-0.5" />
            <div className="min-w-0">
              <div className="font-semibold">
                Approval required: {pendingApproval.label}
              </div>
              <p className="text-[11px] mt-0.5 break-words" style={{ color: "var(--text-muted)" }}>
                {pendingApproval.reason}
              </p>
            </div>
          </div>
          {(onApprove || onReject) && (
            <div className="flex items-center justify-end gap-2">
              {onReject && (
                <button
                  type="button"
                  onClick={() => onReject(pendingApproval)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-[11px] font-medium cursor-pointer"
                  style={{ borderColor: "var(--border-strong)", color: "var(--text-secondary)" }}
                >
                  <X size={12} /> Deny
                </button>
              )}
              {onApprove && (
                <button
                  type="button"
                  onClick={() => onApprove(pendingApproval)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer"
                  style={{ background: "var(--accent-primary)", color: "#ffffff" }}
                >
                  <Check size={12} /> Allow
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {steps.length > 0 && (
        <ActivityFeedV2
          steps={steps}
          orientation={variant === "rail" ? "stacked" : "auto"}
        />
      )}

      {artifacts.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1" aria-label="Produced artifacts">
          {artifacts.map((art) => (
            <a
              key={art.id}
              href={art.downloadUrl || "#"}
              target={art.downloadUrl ? "_blank" : undefined}
              rel={art.downloadUrl ? "noreferrer" : undefined}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--radius-pill)] border text-[11px] font-medium transition-colors"
              style={{
                borderColor: "var(--border-subtle)",
                background: "var(--bg-elevated)",
                color: "var(--text-primary)",
              }}
            >
              <FileText size={12} style={{ color: "var(--accent-primary)" }} />
              <span className="truncate max-w-[180px]">{art.label}</span>
            </a>
          ))}
        </div>
      )}
    </aside>
  );
}
