import React, { useState } from "react";
import {
  FileText,
  Copy,
  Check,
  Download,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  RefreshCw,
  Sparkles,
  Paperclip,
} from "lucide-react";

export interface ExecutiveReportCardProps {
  title?: string;
  modelName?: string;
  latency?: string;
  sourcesCount?: number;
  confidence?: number;
  executiveSummary?: string;
  keyFindings?: string[];
  riskAssessment?: string;
  recommendedActions?: string[];
  sources?: string[];
  onGoodResponse?: () => void;
  onRegenerate?: () => void;
  onExportPdf?: () => void;
}

export const ExecutiveReportCard: React.FC<ExecutiveReportCardProps> = ({
  title = "Q3 Market Position Analysis",
  modelName = "HINA-Reasoner-Pro",
  latency = "4.2s",
  sourcesCount = 4,
  confidence = 87,
  executiveSummary = "Your market share grew 2.4% quarter-over-quarter, outpacing the sector average of 1.1%. The growth was driven primarily by enterprise contract renewals and two new mid-market acquisitions in the APAC region.",
  keyFindings = [
    "Revenue retention reached 94%, up from 89% last quarter",
    "APAC region showed strongest growth at 18.2% MoM",
    "Customer acquisition cost decreased by 12% due to optimized funnel",
    "Two competitors launched aggressive pricing — impact projected at 3% churn risk",
  ],
  riskAssessment = "The competitive pricing pressure from Noronet and DataFlow poses a moderate risk. However, your contract stickiness and switching costs provide a strong buffer. Recommend accelerating the loyalty program rollout.",
  recommendedActions = [
    "Accelerate APAC expansion — allocate 2 additional reps",
    "Launch loyalty program 2 weeks ahead of schedule",
    "Schedule competitive review with product team by Friday",
    "Prepare investor update with Q3 highlight metrics",
  ],
  sources = [
    "Internal CRM",
    "Market Intelligence Feed",
    "Competitor Pricing Database",
    "Financial Dashboard",
  ],
  onGoodResponse,
  onRegenerate,
  onExportPdf,
}) => {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [liked, setLiked] = useState(false);

  const handleCopy = async () => {
    const text = `# ${title}\n\nConfidence: ${confidence}%\n\n## 01 Executive Summary\n${executiveSummary}\n\n## 02 Key Findings\n${keyFindings.map((f) => `- ${f}`).join("\n")}\n\n## 03 Risk Assessment\n${riskAssessment}\n\n## 04 Recommended Actions\n${recommendedActions.map((a) => `- ${a}`).join("\n")}\n\nSources: ${sources.join(", ")}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div style={{ width: "100%", maxWidth: 768, margin: "12px 0 24px 0" }}>
      {/* Assistant Header Line */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 8,
              background: "#1a232b",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Sparkles size={13} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 13, letterSpacing: "0.04em", color: "#1e293b" }}>
                HINA
              </span>
              <span style={{ fontSize: 11, color: "#94a3b8" }}>
                {modelName} · {latency}
              </span>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <button
            type="button"
            onClick={handleCopy}
            title="Copy Report"
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: 4,
              display: "flex",
            }}
          >
            {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
          </button>
          <button
            type="button"
            onClick={onExportPdf}
            title="Download Report"
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: 4,
              display: "flex",
            }}
          >
            <Download size={14} />
          </button>
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? "Expand Report" : "Collapse Report"}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: 4,
              display: "flex",
            }}
          >
            {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>

      {/* Structured White Card */}
      <div
        style={{
          background: "#ffffff",
          borderRadius: 16,
          border: "1px solid #e2e8f0",
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
          padding: "24px 28px",
          overflow: "hidden",
        }}
      >
        {/* Card Header */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 20 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: "#fff1f2",
              color: "#f43f5e",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <FileText size={20} />
          </div>
          <div>
            <h3
              style={{
                fontSize: 16,
                fontWeight: 650,
                color: "#0f172a",
                margin: 0,
                lineHeight: 1.3,
              }}
            >
              {title}
            </h3>
            <p style={{ fontSize: 12, color: "#94a3b8", margin: "3px 0 0 0" }}>
              Generated by {modelName} · {latency} · {sourcesCount} sources
            </p>
          </div>
        </div>

        {!collapsed && (
          <>
            {/* Confidence Meter Box */}
            <div
              style={{
                background: "#f8fafc",
                borderRadius: 10,
                border: "1px solid #f1f5f9",
                padding: "10px 16px",
                marginBottom: 24,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 6,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                    color: "#64748b",
                    textTransform: "uppercase",
                  }}
                >
                  CONFIDENCE
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                  {confidence}%
                </span>
              </div>
              <div
                style={{
                  width: "100%",
                  height: 6,
                  borderRadius: 9999,
                  background: "#e2e8f0",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${confidence}%`,
                    height: "100%",
                    borderRadius: 9999,
                    background: "#10b981",
                    transition: "width 0.5s ease",
                  }}
                />
              </div>
            </div>

            {/* 01 Executive Summary */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", minWidth: 20 }}>
                  01
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                  Executive Summary
                </span>
              </div>
              <p
                style={{
                  fontSize: 13,
                  lineHeight: 1.65,
                  color: "#334155",
                  margin: "0 0 0 32px",
                }}
              >
                {executiveSummary}
              </p>
            </div>

            <div style={{ height: 1, background: "#f1f5f9", margin: "16px 0 20px 32px" }} />

            {/* 02 Key Findings */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", minWidth: 20 }}>
                  02
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                  Key Findings
                </span>
              </div>
              <div style={{ marginLeft: 32, display: "flex", flexDirection: "column", gap: 8 }}>
                {keyFindings.map((finding, idx) => (
                  <div key={idx} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                    <span style={{ color: "#10b981", fontSize: 12, lineHeight: "18px", fontWeight: 700 }}>
                      ✓
                    </span>
                    <span style={{ fontSize: 13, color: "#334155", lineHeight: 1.5 }}>
                      {finding}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ height: 1, background: "#f1f5f9", margin: "16px 0 20px 32px" }} />

            {/* 03 Risk Assessment */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", minWidth: 20 }}>
                  03
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                  Risk Assessment
                </span>
              </div>
              <p
                style={{
                  fontSize: 13,
                  lineHeight: 1.65,
                  color: "#334155",
                  margin: "0 0 0 32px",
                }}
              >
                {riskAssessment}
              </p>
            </div>

            <div style={{ height: 1, background: "#f1f5f9", margin: "16px 0 20px 32px" }} />

            {/* 04 Recommended Actions */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", minWidth: 20 }}>
                  04
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                  Recommended Actions
                </span>
              </div>
              <div style={{ marginLeft: 32, display: "flex", flexDirection: "column", gap: 8 }}>
                {recommendedActions.map((action, idx) => (
                  <div key={idx} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                    <span style={{ color: "#10b981", fontSize: 12, lineHeight: "18px", fontWeight: 700 }}>
                      ✓
                    </span>
                    <span style={{ fontSize: 13, color: "#334155", lineHeight: 1.5 }}>
                      {action}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Sources Footer */}
            {sources.length > 0 && (
              <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid #f1f5f9" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#94a3b8",
                    marginBottom: 8,
                  }}
                >
                  <Paperclip size={12} />
                  <span>Sources</span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {sources.map((src, idx) => (
                    <span
                      key={idx}
                      style={{
                        fontSize: 11,
                        padding: "3px 10px",
                        borderRadius: 6,
                        background: "#f1f5f9",
                        color: "#475569",
                        border: "1px solid #e2e8f0",
                        fontWeight: 500,
                      }}
                    >
                      {src}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Action Buttons Row */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginTop: 20,
                paddingTop: 16,
                borderTop: "1px solid #f1f5f9",
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setLiked(!liked);
                  onGoodResponse?.();
                }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: liked ? "#f0fdf4" : "transparent",
                  border: liked ? "1px solid #86efac" : "1px solid #e2e8f0",
                  color: liked ? "#15803d" : "#475569",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                <ThumbsUp size={13} />
                <span>{liked ? "Liked" : "Good response"}</span>
              </button>

              <button
                type="button"
                onClick={onRegenerate}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: "transparent",
                  border: "1px solid #e2e8f0",
                  color: "#475569",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                <RefreshCw size={13} />
                <span>Regenerate</span>
              </button>

              <button
                type="button"
                onClick={onExportPdf}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: "transparent",
                  border: "1px solid #e2e8f0",
                  color: "#475569",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                <Download size={13} />
                <span>Export PDF</span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
