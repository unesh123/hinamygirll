import { motion } from "framer-motion";
import {
  Check,
  X,
  AlertTriangle,
  Shield,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useState } from "react";

export type ToolRiskLevel = "read" | "local" | "external" | "high";

export interface ToolApprovalRequest {
  id: string;
  toolName: string;
  action: string;
  description: string;
  parameters?: Record<string, unknown>;
  riskLevel: ToolRiskLevel;
  destination?: string;
  requiresApproval: boolean;
}

interface ToolApprovalCardProps {
  request: ToolApprovalRequest;
  status: "pending" | "approved" | "running" | "completed" | "failed" | "cancelled";
  onApprove?: () => void;
  onReject?: () => void;
  result?: string;
  error?: string;
}

const RISK_CONFIG: Record<ToolRiskLevel, { color: string; label: string; icon: React.ReactNode }> = {
  read: { color: "var(--success)", label: "Read-only", icon: <Shield size={14} /> },
  local: { color: "var(--info)", label: "Local change", icon: <Shield size={14} /> },
  external: { color: "var(--warning)", label: "External action", icon: <AlertTriangle size={14} /> },
  high: { color: "var(--danger)", label: "High impact", icon: <AlertTriangle size={14} /> },
};

export function ToolApprovalCard({
  request,
  status,
  onApprove,
  onReject,
  result,
  error,
}: ToolApprovalCardProps) {
  const [showDetails, setShowDetails] = useState(false);
  const risk = RISK_CONFIG[request.riskLevel];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="sakura-tool-card"
      style={{
        background: "var(--bg-elevated)",
        border: `1px solid ${status === "failed" ? "var(--danger)" : status === "completed" ? "var(--success)" : "var(--border-default)"}`,
        borderRadius: "var(--radius-lg)",
        padding: "var(--space-3) var(--space-4)",
        boxShadow: "var(--shadow-xs)",
      }}
    >
      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "var(--space-2)",
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          minWidth: 0,
        }}>
          {/* Status indicator */}
          <div style={{
            width: 28,
            height: 28,
            borderRadius: "var(--radius-sm)",
            background: status === "completed" ? "var(--success-soft)" :
                        status === "failed" ? "var(--danger-soft)" :
                        status === "running" ? "var(--info-soft)" :
                        "var(--bg-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: status === "completed" ? "var(--success)" :
                   status === "failed" ? "var(--danger)" :
                   status === "running" ? "var(--info)" :
                   "var(--text-tertiary)",
            flexShrink: 0,
          }}>
            {status === "completed" ? <Check size={14} /> :
             status === "failed" ? <X size={14} /> :
             status === "running" ? <Loader2 size={14} className="sakura-spin" /> :
             risk.icon}
          </div>

          <div style={{ minWidth: 0 }}>
            <div style={{
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              color: "var(--text-primary)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}>
              {request.toolName}
            </div>
            <div style={{
              fontSize: "var(--text-xs)",
              color: "var(--text-tertiary)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}>
              {request.action}
            </div>
          </div>
        </div>

        {/* Risk badge */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-1)",
          padding: "var(--space-0-5) var(--space-2)",
          borderRadius: "var(--radius-pill)",
          background: risk.color + "18",
          color: risk.color,
          fontSize: "var(--text-xs)",
          fontWeight: 600,
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}>
          {risk.label}
        </div>
      </div>

      {/* Description */}
      <p style={{
        fontSize: "var(--text-sm)",
        color: "var(--text-secondary)",
        lineHeight: "var(--leading-normal)",
        marginTop: "var(--space-2)",
      }}>
        {request.description}
      </p>

      {/* Details toggle */}
      {request.parameters && (
        <button
          onClick={() => setShowDetails(!showDetails)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-1)",
            marginTop: "var(--space-2)",
            padding: 0,
            border: "none",
            background: "transparent",
            color: "var(--text-tertiary)",
            fontSize: "var(--text-xs)",
            fontWeight: 500,
            fontFamily: "var(--font-body)",
            cursor: "pointer",
          }}
        >
          {showDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          Technical details
        </button>
      )}

      {showDetails && request.parameters && (
        <pre style={{
          marginTop: "var(--space-2)",
          padding: "var(--space-3)",
          background: "var(--bg-muted)",
          borderRadius: "var(--radius-sm)",
          fontSize: "var(--text-xs)",
          lineHeight: 1.5,
          overflow: "auto",
          maxHeight: 120,
          color: "var(--text-secondary)",
        }}>
          {JSON.stringify(request.parameters, null, 2)}
        </pre>
      )}

      {/* Result / Error */}
      {result && (
        <div style={{
          marginTop: "var(--space-2)",
          padding: "var(--space-2) var(--space-3)",
          background: "var(--success-soft)",
          borderRadius: "var(--radius-sm)",
          fontSize: "var(--text-sm)",
          color: "var(--success)",
          fontWeight: 500,
        }}>
          {result}
        </div>
      )}

      {error && (
        <div style={{
          marginTop: "var(--space-2)",
          padding: "var(--space-2) var(--space-3)",
          background: "var(--danger-soft)",
          borderRadius: "var(--radius-sm)",
          fontSize: "var(--text-sm)",
          color: "var(--danger)",
        }}>
          {error}
        </div>
      )}

      {/* Actions */}
      {status === "pending" && request.requiresApproval && (
        <div style={{
          display: "flex",
          gap: "var(--space-2)",
          marginTop: "var(--space-3)",
        }}>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onApprove}
            style={{
              flex: 1,
              padding: "var(--space-2) var(--space-4)",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--accent)",
              color: "white",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              fontFamily: "var(--font-body)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--space-1-5)",
            }}
          >
            <Check size={14} />
            Approve
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onReject}
            style={{
              padding: "var(--space-2) var(--space-4)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-default)",
              background: "transparent",
              color: "var(--text-secondary)",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              fontFamily: "var(--font-body)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-1-5)",
            }}
          >
            <X size={14} />
            Reject
          </motion.button>
        </div>
      )}

      <style>{`
        .sakura-spin {
          animation: sakura-spin 1s linear infinite;
        }
        @keyframes sakura-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </motion.div>
  );
}
