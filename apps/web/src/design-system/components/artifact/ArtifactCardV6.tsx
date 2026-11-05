import React from "react";
import {
  FileText,
  Tv,
  FileSpreadsheet,
  FileCode,
  Download,
  Eye,
  Volume2,
  Sparkles,
  BookOpen,
  Compass,
  MessageSquare,
} from "lucide-react";

export type ArtifactType = "document" | "presentation" | "spreadsheet" | "code";

export type ExplanationActionMode =
  | "EXPLAIN_BRIEFLY"
  | "EXPLAIN_FULLY"
  | "EXPLAIN_DIFFERENTLY"
  | "READ_VERBATIM"
  | "DISCUSS";

export interface ArtifactCardV6Props {
  id: string;
  type: ArtifactType;
  title: string;
  summary?: string;
  meta?: string;
  timestamp?: string;
  onPreview?: (id: string) => void;
  onDownload?: (id: string) => void;
  onExplain?: (id: string, mode: ExplanationActionMode) => void;
}

export const ArtifactCardV6: React.FC<ArtifactCardV6Props> = ({
  id,
  type,
  title,
  summary,
  meta,
  timestamp,
  onPreview,
  onDownload,
  onExplain,
}) => {
  const getIcon = () => {
    switch (type) {
      case "presentation":
        return <Tv size={16} />;
      case "spreadsheet":
        return <FileSpreadsheet size={16} />;
      case "code":
        return <FileCode size={16} />;
      case "document":
      default:
        return <FileText size={16} />;
    }
  };

  const handleExplainAction = (mode: ExplanationActionMode) => {
    if (onExplain) {
      onExplain(id, mode);
    } else if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("hinaa:explain-artifact", {
          detail: { artifactId: id, title, summary, mode },
        })
      );
    }
  };

  return (
    <div
      className="artifact-card-v6"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        padding: "14px",
        background: "var(--surface-card, #ffffff)",
        borderRadius: "var(--radius-lg, 16px)",
        border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "var(--radius-sm, 8px)",
              background: "var(--accent-subtle, #fff2f6)",
              color: "var(--accent-primary, #dc5f8b)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {getIcon()}
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
              {title}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
              {meta || `${type.charAt(0).toUpperCase() + type.slice(1)} Artifact`}
              {timestamp && ` • ${timestamp}`}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 6 }}>
          {onPreview && (
            <button
              type="button"
              onClick={() => onPreview(id)}
              title="Preview Artifact"
              style={{
                background: "var(--surface-subtle)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm, 8px)",
                padding: "5px 10px",
                display: "flex",
                alignItems: "center",
                gap: 5,
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
            >
              <Eye size={12} />
              <span>Preview</span>
            </button>
          )}

          {onDownload && (
            <button
              type="button"
              onClick={() => onDownload(id)}
              title="Download Artifact"
              style={{
                background: "var(--surface-subtle)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm, 8px)",
                padding: "5px 10px",
                display: "flex",
                alignItems: "center",
                gap: 5,
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
            >
              <Download size={12} />
              <span>Export</span>
            </button>
          )}
        </div>
      </div>

      {summary && (
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
          {summary}
        </div>
      )}

      {/* Reflective Voice & Metacognitive Explanation Action Row (Module H) */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          paddingTop: 8,
          borderTop: "1px solid var(--border-subtle, rgba(0,0,0,0.06))",
        }}
      >
        <button
          type="button"
          onClick={() => handleExplainAction("EXPLAIN_BRIEFLY")}
          title="Explain main takeaways briefly"
          style={{
            background: "var(--accent-subtle, #f5f3ff)",
            border: "1px solid var(--border-subtle, #ddd6fe)",
            borderRadius: "var(--radius-sm, 6px)",
            padding: "4px 8px",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            fontWeight: 600,
            color: "var(--accent-primary, #6d28d9)",
            cursor: "pointer",
          }}
        >
          <Volume2 size={12} />
          <span>Brief Explanation</span>
        </button>

        <button
          type="button"
          onClick={() => handleExplainAction("EXPLAIN_FULLY")}
          title="Section by section walkthrough"
          style={{
            background: "var(--surface-subtle, #f8fafc)",
            border: "1px solid var(--border-subtle, #e2e8f0)",
            borderRadius: "var(--radius-sm, 6px)",
            padding: "4px 8px",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            fontWeight: 500,
            color: "var(--text-primary, #1e293b)",
            cursor: "pointer",
          }}
        >
          <BookOpen size={12} />
          <span>Detailed Walkthrough</span>
        </button>

        <button
          type="button"
          onClick={() => handleExplainAction("EXPLAIN_DIFFERENTLY")}
          title="Alternative analogy-based perspective"
          style={{
            background: "var(--surface-subtle, #f8fafc)",
            border: "1px solid var(--border-subtle, #e2e8f0)",
            borderRadius: "var(--radius-sm, 6px)",
            padding: "4px 8px",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            fontWeight: 500,
            color: "var(--text-primary, #1e293b)",
            cursor: "pointer",
          }}
        >
          <Compass size={12} />
          <span>Another Perspective</span>
        </button>

        <button
          type="button"
          onClick={() => handleExplainAction("READ_VERBATIM")}
          title="Read document out loud word for word"
          style={{
            background: "var(--surface-subtle, #f8fafc)",
            border: "1px solid var(--border-subtle, #e2e8f0)",
            borderRadius: "var(--radius-sm, 6px)",
            padding: "4px 8px",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            fontWeight: 500,
            color: "var(--text-secondary, #64748b)",
            cursor: "pointer",
          }}
        >
          <Sparkles size={12} />
          <span>Read Verbatim</span>
        </button>

        <button
          type="button"
          onClick={() => handleExplainAction("DISCUSS")}
          title="Interactive discussion with Hina"
          style={{
            background: "var(--surface-subtle, #f8fafc)",
            border: "1px solid var(--border-subtle, #e2e8f0)",
            borderRadius: "var(--radius-sm, 6px)",
            padding: "4px 8px",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            fontWeight: 500,
            color: "var(--text-primary, #1e293b)",
            cursor: "pointer",
          }}
        >
          <MessageSquare size={12} />
          <span>Discuss with Hina</span>
        </button>
      </div>
    </div>
  );
};
