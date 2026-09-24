import React from "react";
import {
  FileText,
  Tv,
  FileSpreadsheet,
  FileCode,
  Download,
  Eye,
  ExternalLink,
  Layers,
} from "lucide-react";

export type ArtifactType = "document" | "presentation" | "spreadsheet" | "code";

export interface ArtifactCardV6Props {
  id: string;
  type: ArtifactType;
  title: string;
  summary?: string;
  meta?: string; // e.g. "12 slides · 1.4 MB" or "4 pages · 1,240 words"
  timestamp?: string;
  onPreview?: (id: string) => void;
  onDownload?: (id: string) => void;
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
              {timestamp && ` · ${timestamp}`}
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
    </div>
  );
};
