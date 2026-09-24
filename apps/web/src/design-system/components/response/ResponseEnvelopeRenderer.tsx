import React, { memo, useMemo } from "react";
import {
  MediaGalleryV6,
  type MediaGalleryItem,
} from "../media/MediaGalleryV6";
import {
  CodingTaskCard,
  type TaskStep,
} from "../task/CodingTaskCard";
import {
  ApprovalCard,
  type ApprovalRiskLevel,
} from "../approval/ApprovalCard";
import {
  ArtifactCardV6,
  type ArtifactType,
} from "../artifact/ArtifactCardV6";
import {
  CitationPopover,
  type CitationSource,
} from "../source/CitationPopover";
import { AlertTriangle, XCircle, Info, ExternalLink, Globe } from "lucide-react";
import { ResponseMarkdown } from "@/components/ui/ResponseMarkdown";

/* ── Typed Envelope Block Definitions ──────────────────── */
export interface ResponseEnvelopeBlock {
  id?: string;
  kind:
    | "text"
    | "research"
    | "media_gallery"
    | "coding_task"
    | "approval"
    | "artifact"
    | "warning"
    | "error"
    | "code"
    | "terminal"
    | "diff";
  // Text block
  content?: string;
  // Research block
  sources?: Array<{
    id: string;
    title: string;
    url?: string;
    domain?: string;
    snippet?: string;
    date?: string;
  }>;
  // Media Gallery block
  mediaItems?: MediaGalleryItem[];
  selectedMediaId?: string | null;
  // Coding Task block
  taskTitle?: string;
  taskStatus?: "running" | "completed" | "failed" | "paused";
  taskSteps?: TaskStep[];
  filesChangedCount?: number;
  testsPassed?: number;
  totalTests?: number;
  diffSnippet?: string;
  // Approval block
  approvalId?: string;
  approvalAction?: string;
  approvalTarget?: string;
  approvalRiskLevel?: ApprovalRiskLevel;
  approvalReason?: string;
  // Artifact block
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactTitle?: string;
  artifactSummary?: string;
  artifactMeta?: string;
  // Alert / Message
  title?: string;
  message?: string;
  code?: string;
  // Terminal / code
  filename?: string;
  language?: string;
  command?: string;
  output?: string;
}

export interface ResponseEnvelopeRendererProps {
  blocks?: ResponseEnvelopeBlock[];
  rawText?: string;
  toolResult?: any;
  toolName?: string;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  onMediaSelect?: (item: MediaGalleryItem) => void;
  onMediaReference?: (item: MediaGalleryItem) => void;
  onArtifactPreview?: (id: string) => void;
  onArtifactDownload?: (id: string) => void;
  className?: string;
}

/* ── Component ─────────────────────────────────────────── */
export const ResponseEnvelopeRenderer: React.FC<ResponseEnvelopeRendererProps> = memo(
  ({
    blocks: directBlocks,
    rawText,
    toolResult,
    toolName,
    onApprove,
    onReject,
    onMediaSelect,
    onMediaReference,
    onArtifactPreview,
    onArtifactDownload,
    className = "response-envelope-renderer",
  }) => {
    // Derive blocks from directBlocks, toolResult, or rawText
    const resolvedBlocks = useMemo<ResponseEnvelopeBlock[]>(() => {
      if (directBlocks && directBlocks.length > 0) {
        return directBlocks;
      }

      // Convert toolResult if present
      if (toolResult) {
        const data = toolResult.data !== undefined ? toolResult.data : toolResult;
        const normalizedBlocks: ResponseEnvelopeBlock[] = [];

        // 1. Approval Gate
        if (toolResult.status === "RequiresApproval" || data.status === "RequiresApproval") {
          normalizedBlocks.push({
            id: toolResult.approvalId || "appr-1",
            kind: "approval",
            approvalId: toolResult.approvalId || "appr-1",
            approvalAction: data.action ? `${data.action} ${data.args || ""}` : `Execute ${toolName || "action"}`,
            approvalTarget: toolName || "external_tool",
            approvalRiskLevel: (data.riskLevel as ApprovalRiskLevel) || "high",
            approvalReason: data.reason || "This operation alters system state or accesses external resources and requires authorization.",
          });
          return normalizedBlocks;
        }

        // 2. Media Gallery from image_search / public-images
        if (toolName === "image_search" || (data && Array.isArray(data.images))) {
          const items: MediaGalleryItem[] = (data.images || []).map((img: any, idx: number) => {
            const isObj = typeof img === "object" && img !== null;
            const url = isObj ? img.imageUrl || img.url || img.thumbnailUrl : String(img);
            const source = isObj ? img.source || "Web" : "Web";
            const isNews = /news|reuters|bbc|apnews|cnn|aljazeera/i.test(source) || /news/i.test(url);
            const isGen = /generated|comfy|magnific|flux/i.test(url);
            return {
              id: isObj && img.id ? img.id : `img-${idx + 1}`,
              url,
              thumbnailUrl: isObj ? img.thumbnailUrl || url : url,
              title: isObj && img.title ? img.title : `Image ${idx + 1}`,
              source,
              sourceCategory: isGen ? "generated" : isNews ? "news" : "web",
            };
          });

          normalizedBlocks.push({
            id: `media-gallery-${toolName || "search"}`,
            kind: "media_gallery",
            mediaItems: items,
          });
        }

        // 3. Research Sources from web_search
        if (toolName === "web_search" && Array.isArray(data.sources)) {
          const sources = data.sources.map((s: any, idx: number) => ({
            id: s.id || `S${idx + 1}`,
            title: s.title || "Untitled source",
            url: s.url || "#",
            domain: s.domain || (s.url ? new URL(s.url).hostname.replace(/^www\./, "") : "Web"),
            snippet: s.snippet || "",
          }));

          normalizedBlocks.push({
            id: `research-sources`,
            kind: "research",
            sources,
          });
        }

        // 4. Artifact Document / Presentation
        if (toolName === "document_generate" || toolName === "pdf_generate" || toolName?.includes("gamma")) {
          normalizedBlocks.push({
            id: data.id || `artifact-${toolName}`,
            kind: "artifact",
            artifactId: data.id || `art-${Date.now()}`,
            artifactType: toolName.includes("gamma") ? "presentation" : "document",
            artifactTitle: data.title || "Generated Document",
            artifactSummary: data.summary || data.snippet || "Exported artifact ready for preview or download.",
            artifactMeta: data.meta || (data.pageCount ? `${data.pageCount} pages` : "Document"),
          });
        }

        // 5. Coding Task Execution
        if (data && (data.taskType === "coding_task" || (Array.isArray(data.steps) && data.steps.length > 0))) {
          normalizedBlocks.push({
            id: data.id || "coding-task-card",
            kind: "coding_task",
            taskTitle: data.goal || data.title || "Code Generation Task",
            taskStatus: data.status === "completed" ? "completed" : data.status === "failed" ? "failed" : "running",
            taskSteps: (data.steps || []).map((s: any, idx: number) => ({
              id: s.id || `s-${idx}`,
              label: s.title || s.description || `Step ${idx + 1}`,
              status: s.status || "pending",
              details: s.failureReason,
            })),
            filesChangedCount: data.filesChangedCount || 0,
            testsPassed: data.testsPassed,
            totalTests: data.totalTests,
            diffSnippet: data.diffSnippet,
          });
        }

        if (normalizedBlocks.length > 0) {
          return normalizedBlocks;
        }
      }

      // Fallback: standard markdown text block
      if (rawText && rawText.trim()) {
        return [
          {
            id: "raw-text-block",
            kind: "text",
            content: rawText,
          },
        ];
      }

      return [];
    }, [directBlocks, toolResult, toolName, rawText]);

    if (resolvedBlocks.length === 0) {
      return null;
    }

    return (
      <div
        className={className}
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          width: "100%",
        }}
      >
        {resolvedBlocks.map((block, idx) => {
          const key = block.id || `envelope-block-${block.kind}-${idx}`;

          switch (block.kind) {
            case "media_gallery":
              return (
                <MediaGalleryV6
                  key={key}
                  items={block.mediaItems || []}
                  selectedId={block.selectedMediaId}
                  onSelect={onMediaSelect}
                  onUseAsReference={onMediaReference}
                  onOpenSource={(item) => {
                    if (item.url) window.open(item.url, "_blank", "noopener,noreferrer");
                  }}
                />
              );

            case "coding_task":
              return (
                <CodingTaskCard
                  key={key}
                  title={block.taskTitle || "Durable Task"}
                  status={block.taskStatus || "running"}
                  steps={block.taskSteps || []}
                  filesChangedCount={block.filesChangedCount}
                  testsPassed={block.testsPassed}
                  totalTests={block.totalTests}
                  diffSnippet={block.diffSnippet}
                />
              );

            case "approval":
              return (
                <ApprovalCard
                  key={key}
                  id={block.approvalId || `appr-${idx}`}
                  action={block.approvalAction || "Authorize Action"}
                  target={block.approvalTarget}
                  riskLevel={block.approvalRiskLevel || "high"}
                  reason={block.approvalReason}
                  onApprove={(id) => onApprove?.(id)}
                  onReject={(id) => onReject?.(id)}
                />
              );

            case "artifact":
              return (
                <ArtifactCardV6
                  key={key}
                  id={block.artifactId || `art-${idx}`}
                  type={block.artifactType || "document"}
                  title={block.artifactTitle || "Document"}
                  summary={block.artifactSummary}
                  meta={block.artifactMeta}
                  onPreview={onArtifactPreview}
                  onDownload={onArtifactDownload}
                />
              );

            case "research":
              return (
                <div
                  key={key}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    padding: 12,
                    background: "rgba(255,255,255,0.02)",
                    borderRadius: 12,
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-tertiary, #a1a1aa)" }}>
                    <Globe size={13} color="var(--accent, #ec4899)" />
                    <span>Attributable Web Sources ({block.sources?.length || 0})</span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 8 }}>
                    {(block.sources || []).map((s) => (
                      <a
                        key={s.id}
                        href={s.url || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          padding: "8px 10px",
                          borderRadius: 8,
                          background: "var(--bg-surface, #18181b)",
                          border: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
                          textDecoration: "none",
                          color: "inherit",
                          display: "flex",
                          flexDirection: "column",
                          gap: 4,
                          transition: "border-color 150ms ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent, #ec4899)" }}>
                            [{s.id}] {s.domain}
                          </span>
                          <ExternalLink size={10} color="#71717a" />
                        </div>
                        <span style={{ fontSize: "11px", fontWeight: 600, color: "#fff", lineHeight: 1.3, display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                          {s.title}
                        </span>
                        {s.snippet && (
                          <span style={{ fontSize: "10px", color: "var(--text-secondary, #a1a1aa)", lineHeight: 1.4, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                            {s.snippet}
                          </span>
                        )}
                      </a>
                    ))}
                  </div>
                </div>
              );

            case "warning":
              return (
                <div
                  key={key}
                  style={{
                    padding: "10px 14px",
                    borderRadius: 8,
                    background: "rgba(245,158,11,0.1)",
                    border: "1px solid rgba(245,158,11,0.3)",
                    color: "#fef3c7",
                    fontSize: "12px",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                  }}
                >
                  <AlertTriangle size={15} color="#f59e0b" style={{ flexShrink: 0, marginTop: 1 }} />
                  <div>
                    {block.title && <div style={{ fontWeight: 700, marginBottom: 2 }}>{block.title}</div>}
                    <div>{block.message}</div>
                  </div>
                </div>
              );

            case "error":
              return (
                <div
                  key={key}
                  style={{
                    padding: "10px 14px",
                    borderRadius: 8,
                    background: "rgba(239,68,68,0.1)",
                    border: "1px solid rgba(239,68,68,0.3)",
                    color: "#fee2e2",
                    fontSize: "12px",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                  }}
                >
                  <XCircle size={15} color="#ef4444" style={{ flexShrink: 0, marginTop: 1 }} />
                  <div>
                    {block.code && <span style={{ fontFamily: "monospace", fontSize: "11px", color: "#fca5a5", marginRight: 6 }}>[{block.code}]</span>}
                    {block.title && <strong style={{ marginRight: 6 }}>{block.title}:</strong>}
                    <span>{block.message}</span>
                  </div>
                </div>
              );

            case "text":
            default:
              return (
                <div key={key} style={{ fontSize: "14px", lineHeight: "1.6", color: "inherit" }}>
                  <ResponseMarkdown text={block.content || ""} />
                </div>
              );
          }
        })}
      </div>
    );
  }
);
