import React, { useState } from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  FileCode,
  Terminal,
  GitCommit,
  Play,
  Square,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

export interface TaskStep {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  details?: string;
}

export interface CodingTaskCardProps {
  title: string;
  status: "running" | "completed" | "failed" | "paused";
  steps: TaskStep[];
  filesChangedCount?: number;
  testsPassed?: number;
  totalTests?: number;
  diffSnippet?: string;
  onViewDiff?: () => void;
  onCommit?: () => void;
  onStop?: () => void;
}

export const CodingTaskCard: React.FC<CodingTaskCardProps> = ({
  title,
  status,
  steps,
  filesChangedCount = 0,
  testsPassed = 0,
  totalTests = 0,
  diffSnippet,
  onViewDiff,
  onCommit,
  onStop,
}) => {
  const [diffExpanded, setDiffExpanded] = useState(false);

  return (
    <div
      className="coding-task-card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        padding: "14px",
        background: "var(--surface-card, #ffffff)",
        borderRadius: "var(--radius-lg, 16px)",
        border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
        boxShadow: "var(--shadow-card)",
      }}
    >
      {/* ── Header: Title, Status Badge, Controls ───────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "var(--radius-sm, 8px)",
              background: "var(--surface-subtle, #f6f3f7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--accent-primary, #dc5f8b)",
            }}
          >
            <Terminal size={15} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{title}</div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
              {filesChangedCount > 0 && `${filesChangedCount} files changed · `}
              {totalTests > 0 && `${testsPassed}/${totalTests} tests passing`}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "3px 8px",
              borderRadius: "var(--radius-full, 9999px)",
              fontSize: 11,
              fontWeight: 600,
              background:
                status === "completed"
                  ? "var(--semantic-success-bg, #f0fdf4)"
                  : status === "running"
                  ? "var(--accent-subtle, #fff2f6)"
                  : "var(--surface-subtle)",
              color:
                status === "completed"
                  ? "var(--semantic-success-fg, #15803d)"
                  : status === "running"
                  ? "var(--accent-primary, #dc5f8b)"
                  : "var(--text-secondary)",
              border: `1px solid ${
                status === "completed"
                  ? "var(--semantic-success-border, #bbf7d0)"
                  : status === "running"
                  ? "var(--border-accent, rgba(220, 95, 139, 0.35))"
                  : "var(--border-subtle)"
              }`,
            }}
          >
            {status === "running" && <Loader2 size={11} className="animate-spin" />}
            {status === "completed" && <CheckCircle2 size={11} />}
            <span style={{ textTransform: "capitalize" }}>{status}</span>
          </div>

          {status === "running" && onStop && (
            <button
              type="button"
              onClick={onStop}
              title="Stop Task"
              style={{
                background: "var(--semantic-danger-bg, #fef2f2)",
                border: "1px solid var(--semantic-danger-border, #fecaca)",
                color: "var(--semantic-danger-fg, #b91c1c)",
                borderRadius: "var(--radius-sm, 8px)",
                padding: "4px 8px",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Stop
            </button>
          )}
        </div>
      </div>

      {/* ── Multi-stage Step Checklist ──────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
          padding: "8px 10px",
          background: "var(--surface-subtle, #f6f3f7)",
          borderRadius: "var(--radius-md, 12px)",
        }}
      >
        {steps.map((step) => {
          return (
            <div
              key={step.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color:
                  step.status === "completed"
                    ? "var(--text-primary)"
                    : step.status === "running"
                    ? "var(--accent-primary)"
                    : "var(--text-tertiary)",
              }}
            >
              {step.status === "completed" && (
                <CheckCircle2 size={13} style={{ color: "var(--semantic-success-fg)" }} />
              )}
              {step.status === "running" && (
                <Loader2 size={13} className="animate-spin" style={{ color: "var(--accent-primary)" }} />
              )}
              {step.status === "failed" && (
                <XCircle size={13} style={{ color: "var(--semantic-danger-fg)" }} />
              )}
              {step.status === "pending" && <Circle size={13} style={{ opacity: 0.3 }} />}

              <span style={{ fontWeight: step.status === "running" ? 600 : 400 }}>{step.label}</span>
              {step.details && (
                <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: "auto" }}>
                  {step.details}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Collapsible Diff Viewer ─────────────────────────────────────── */}
      {diffSnippet && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <button
            type="button"
            onClick={() => setDiffExpanded(!diffExpanded)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              background: "none",
              border: "none",
              padding: 0,
              fontSize: 11,
              fontWeight: 600,
              color: "var(--accent-primary)",
              cursor: "pointer",
            }}
          >
            {diffExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            <span>{diffExpanded ? "Hide Code Diff" : "View Code Diff"}</span>
          </button>

          {diffExpanded && (
            <pre
              style={{
                margin: 0,
                padding: "8px 12px",
                background: "var(--surface-active, #f1ebf1)",
                borderRadius: "var(--radius-sm, 8px)",
                fontSize: 11,
                fontFamily: "monospace",
                overflowX: "auto",
                maxHeight: 200,
                color: "var(--text-primary)",
              }}
            >
              <code>{diffSnippet}</code>
            </pre>
          )}
        </div>
      )}

      {/* ── Task Actions: View Diff, Commit ─────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8, paddingTop: 4 }}>
        {onViewDiff && (
          <button
            type="button"
            onClick={onViewDiff}
            style={{
              padding: "5px 12px",
              borderRadius: "var(--radius-sm, 8px)",
              background: "var(--surface-subtle)",
              border: "1px solid var(--border-default)",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--text-primary)",
              cursor: "pointer",
            }}
          >
            Full Diff
          </button>
        )}

        {status === "completed" && onCommit && (
          <button
            type="button"
            onClick={onCommit}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "5px 12px",
              borderRadius: "var(--radius-sm, 8px)",
              background: "var(--accent-primary, #dc5f8b)",
              color: "#ffffff",
              border: "none",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <GitCommit size={13} />
            <span>Commit Changes</span>
          </button>
        )}
      </div>
    </div>
  );
};
