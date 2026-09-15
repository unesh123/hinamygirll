import React from "react";
import { AlertTriangle, CheckCircle2, XCircle, ShieldAlert } from "lucide-react";

export type ApprovalRiskLevel = "low" | "medium" | "high" | "critical";

export interface ApprovalCardProps {
  id: string;
  action: string;
  target?: string;
  riskLevel: ApprovalRiskLevel;
  reason?: string;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  disabled?: boolean;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  id,
  action,
  target,
  riskLevel,
  reason,
  onApprove,
  onReject,
  disabled = false,
}) => {
  const getRiskColors = () => {
    switch (riskLevel) {
      case "critical":
      case "high":
        return {
          bg: "var(--semantic-danger-bg, #fef2f2)",
          fg: "var(--semantic-danger-fg, #b91c1c)",
          border: "var(--semantic-danger-border, #fecaca)",
        };
      case "medium":
        return {
          bg: "var(--semantic-warning-bg, #fffbeb)",
          fg: "var(--semantic-warning-fg, #b45309)",
          border: "var(--semantic-warning-border, #fde68a)",
        };
      case "low":
      default:
        return {
          bg: "var(--semantic-info-bg, #eff6ff)",
          fg: "var(--semantic-info-fg, #1d4ed8)",
          border: "var(--semantic-info-border, #bfdbfe)",
        };
    }
  };

  const colors = getRiskColors();

  return (
    <div
      className="approval-card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        padding: "14px",
        background: "var(--surface-card, #ffffff)",
        borderRadius: "var(--radius-lg, 16px)",
        border: `1px solid ${colors.border}`,
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              background: colors.bg,
              color: colors.fg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ShieldAlert size={16} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
              Approval Required: {action}
            </div>
            {target && (
              <div style={{ fontSize: 11, fontFamily: "monospace", color: "var(--text-secondary)" }}>
                Target: {target}
              </div>
            )}
          </div>
        </div>

        <div
          style={{
            padding: "2px 8px",
            borderRadius: "var(--radius-full, 9999px)",
            background: colors.bg,
            color: colors.fg,
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.04em",
          }}
        >
          {riskLevel} risk
        </div>
      </div>

      {reason && (
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
          {reason}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8, paddingTop: 4 }}>
        <button
          type="button"
          onClick={() => onReject(id)}
          disabled={disabled}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            padding: "5px 12px",
            borderRadius: "var(--radius-sm, 8px)",
            background: "var(--surface-subtle)",
            border: "1px solid var(--border-default)",
            color: "var(--text-secondary)",
            fontSize: 12,
            fontWeight: 600,
            cursor: disabled ? "not-allowed" : "pointer",
          }}
        >
          <XCircle size={13} />
          <span>Reject</span>
        </button>

        <button
          type="button"
          onClick={() => onApprove(id)}
          disabled={disabled}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            padding: "5px 14px",
            borderRadius: "var(--radius-sm, 8px)",
            background: "var(--accent-primary, #dc5f8b)",
            color: "#ffffff",
            border: "none",
            fontSize: 12,
            fontWeight: 600,
            cursor: disabled ? "not-allowed" : "pointer",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <CheckCircle2 size={13} />
          <span>Approve Action</span>
        </button>
      </div>
    </div>
  );
};
