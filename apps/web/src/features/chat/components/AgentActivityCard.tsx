import { useState, useEffect, useMemo } from "react";
import { Loader2, CheckCircle2, XCircle, StopCircle, Sparkles, Wrench, FileSearch } from "lucide-react";

export interface ActivityStep {
  id: string;
  toolName?: string;
  title: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  message?: string;
  stepNumber?: number;
  totalSteps?: number;
}

export interface AgentActivityCardProps {
  isActive: boolean;
  steps: ActivityStep[];
  currentAction?: string;
  elapsedMs?: number;
  onCancel?: () => void;
  onResume?: () => void;
  onConfirm?: () => void;
  onReject?: () => void;
  onRecover?: () => void;
}

export function AgentActivityCard({
  isActive,
  steps,
  currentAction = "Thinking & Planning...",
  elapsedMs: initialElapsedMs,
  onCancel,
  onResume,
  onConfirm,
  onReject,
  onRecover,
}: AgentActivityCardProps) {
  const [timerSec, setTimerSec] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setTimerSec(0);
      return;
    }
    const interval = setInterval(() => {
      setTimerSec((s) => s + 0.1);
    }, 100);
    return () => clearInterval(interval);
  }, [isActive]);

  // Keep the pre-flight state honest: until the server emits steps we show an
  // indeterminate stage instead of inventing completed work or fake percentages.
  const effectiveSteps: ActivityStep[] = useMemo(() => {
    if (steps.length > 0) return steps;
    if (!isActive) return [];
    return [
      {
        id: "awaiting-live-progress",
        title: "Waiting for live execution updates",
        status: "running",
        message: "The runner has started; progress will appear as each tool reports",
        stepNumber: 1,
        totalSteps: 1,
      },
    ];
  }, [steps, isActive]);

  // If inactive and no steps, do not render
  if (!isActive && steps.length === 0) return null;

  const currentStep = effectiveSteps[effectiveSteps.length - 1];
  const hasFailed = effectiveSteps.some((step) => step.status === "failed");
  const hasPendingApproval = effectiveSteps.some((step) => step.status === "pending");
  const hasCancelled = effectiveSteps.some((step) => step.status === "cancelled");
  const stepNumber = currentStep?.stepNumber || effectiveSteps.length || 1;
  const totalSteps = currentStep?.totalSteps || Math.max(stepNumber, 2);

  const completedCount = effectiveSteps.filter((s) => s.status === "completed").length;
  const progressPercent = Math.min(
    100,
    Math.max(
      8,
      effectiveSteps.length > 0
        ? Math.round((completedCount / effectiveSteps.length) * 100) + (isActive ? 15 : 0)
        : 25
    )
  );

  return (
    <div
      data-testid="agent-activity-card"
      style={{
        position: "relative",
        overflow: "hidden",
        background: "linear-gradient(135deg, rgba(248, 250, 252, 0.96), rgba(241, 245, 249, 0.94))",
        border: "1px solid rgba(99, 102, 241, 0.25)",
        borderRadius: 14,
        padding: "10px 14px",
        marginBottom: 12,
        boxShadow: isActive
          ? "0 8px 24px -4px rgba(99, 102, 241, 0.12), 0 2px 8px -2px rgba(0, 0, 0, 0.04)"
          : "0 4px 12px -2px rgba(0, 0, 0, 0.05)",
        backdropFilter: "blur(12px)",
        transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {/* Dynamic top progress glow bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          height: 3,
          width: isActive ? `${progressPercent}%` : "100%",
          background: isActive
            ? "linear-gradient(90deg, #6366f1, #a855f7, #ec4899)"
            : "linear-gradient(90deg, #10b981, #059669)",
          transition: "width 0.4s ease",
          boxShadow: isActive ? "0 0 8px rgba(168, 85, 247, 0.6)" : "none",
        }}
      />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 24,
              height: 24,
              borderRadius: "50%",
              background: isActive
                ? "linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(236, 72, 153, 0.2))"
                : "rgba(16, 185, 129, 0.15)",
              color: isActive ? "#6366f1" : "#10b981",
              boxShadow: isActive ? "0 0 10px rgba(99, 102, 241, 0.3)" : "none",
            }}
          >
            {isActive ? (
              <Loader2 size={13} className="animate-spin" style={{ animationDuration: "0.9s" }} />
            ) : (
              <CheckCircle2 size={14} />
            )}
          </span>
          <div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "-0.01em",
                color: "var(--text-primary, #0f172a)",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
        <span>{isActive ? "HINAA Active Execution" : hasFailed ? "Execution Failed" : hasCancelled ? "Execution Stopped" : "Execution Completed"}</span>
              {isActive && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 3,
                    fontSize: 9,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    padding: "1px 6px",
                    borderRadius: 10,
                    background: "rgba(99, 102, 241, 0.12)",
                    color: "#6366f1",
                  }}
                >
                  <Sparkles size={9} />
                  Live
                </span>
              )}
            </div>
            <div style={{ fontSize: 10, fontWeight: 500, color: "var(--text-muted, #64748b)" }}>
              Step {stepNumber} of {totalSteps} • {timerSec.toFixed(1)}s elapsed
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
        {hasPendingApproval && onConfirm && (
          <button
            type="button"
            data-testid="confirm-activity-btn"
            onClick={onConfirm}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: "rgba(16, 185, 129, 0.1)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              borderRadius: 6,
              padding: "4px 9px",
              fontSize: 11,
              fontWeight: 600,
              color: "#059669",
              cursor: "pointer",
            }}
          >
            Approve
          </button>
        )}
        {hasPendingApproval && onReject && (
          <button
            type="button"
            data-testid="reject-activity-btn"
            onClick={onReject}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              borderRadius: 6,
              padding: "4px 9px",
              fontSize: 11,
              fontWeight: 600,
              color: "#dc2626",
              cursor: "pointer",
            }}
          >
            Reject
          </button>
        )}
        {!isActive && hasFailed && onRecover && (
          <button
            type="button"
            data-testid="recover-activity-btn"
            onClick={onRecover}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: "rgba(245, 158, 11, 0.1)",
              border: "1px solid rgba(245, 158, 11, 0.28)",
              borderRadius: 6,
              padding: "4px 9px",
              fontSize: 11,
              fontWeight: 600,
              color: "#b45309",
              cursor: "pointer",
            }}
          >
            Recover
          </button>
        )}
        {isActive && onCancel && (
          <button
            type="button"
            data-testid="cancel-activity-btn"
            onClick={onCancel}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              borderRadius: 6,
              padding: "4px 9px",
              fontSize: 11,
              fontWeight: 600,
              color: "#dc2626",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <StopCircle size={12} />
            <span>Cancel</span>
          </button>
        )}
        </div>
      </div>

      {/* Step items with status icons and clean styling */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 6 }}>
        {effectiveSteps.map((st) => {
          const isDone = st.status === "completed";
          const isFail = st.status === "failed";
          const isCancelled = st.status === "cancelled";
          const isPending = st.status === "pending";
          return (
            <div
              key={st.id}
              data-testid={`activity-step-${st.id}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                fontSize: 11,
                padding: "2px 4px",
                borderRadius: 6,
                background: !isDone && !isFail && !isCancelled ? "rgba(99, 102, 241, 0.04)" : "transparent",
                color: isDone ? "#059669" : isFail ? "#dc2626" : isCancelled ? "#64748b" : "#334155",
              }}
            >
              {isDone ? (
                <CheckCircle2 size={13} style={{ color: "#10b981", flexShrink: 0 }} />
              ) : isFail ? (
                <XCircle size={13} style={{ color: "#ef4444", flexShrink: 0 }} />
              ) : isCancelled ? (
                <StopCircle size={13} style={{ color: "#64748b", flexShrink: 0 }} />
              ) : isPending ? (
                <Wrench size={13} style={{ color: "#a855f7", flexShrink: 0 }} />
              ) : (
                <Loader2
                  size={13}
                  className="animate-spin"
                  style={{ color: "#6366f1", flexShrink: 0, animationDuration: "1s" }}
                />
              )}
              <span style={{ fontWeight: isDone ? 600 : 700 }}>{st.title}</span>
              {st.message && (
                <span
                  style={{
                    color: isDone ? "#10b981" : isFail ? "#ef4444" : "#64748b",
                    fontSize: 10,
                    fontWeight: 500,
                  }}
                >
                  — {st.message}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
