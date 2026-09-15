import React, { useState } from "react";
import {
  ExternalLink,
  CheckCircle2,
  Sparkles,
  Search,
  Layers,
  Eye,
  Maximize2,
  Bookmark,
} from "lucide-react";

export type MediaSourceCategory = "all" | "web" | "news" | "stock" | "generated";

export interface MediaGalleryItem {
  id: string;
  url: string;
  thumbnailUrl?: string;
  title: string;
  source?: string;
  sourceCategory?: "web" | "news" | "stock" | "generated";
  aspectRatio?: string;
  isSelected?: boolean;
}

export interface MediaGalleryV6Props {
  items: MediaGalleryItem[];
  selectedId?: string | null;
  onSelect?: (item: MediaGalleryItem) => void;
  onUseAsReference?: (item: MediaGalleryItem) => void;
  onUpscale?: (item: MediaGalleryItem) => void;
  onOpenSource?: (item: MediaGalleryItem) => void;
}

export const MediaGalleryV6: React.FC<MediaGalleryV6Props> = ({
  items,
  selectedId,
  onSelect,
  onUseAsReference,
  onUpscale,
  onOpenSource,
}) => {
  const [activeTab, setActiveTab] = useState<MediaSourceCategory>("all");
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const filteredItems = items.filter((it) => {
    if (activeTab === "all") return true;
    return (it.sourceCategory || "web") === activeTab;
  });

  return (
    <div
      className="media-gallery-v6"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        padding: "12px",
        background: "var(--surface-card, #ffffff)",
        borderRadius: "var(--radius-lg, 16px)",
        border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
        boxShadow: "var(--shadow-card)",
      }}
    >
      {/* ── Category Filter Tabs ────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 2,
            padding: 2,
            borderRadius: "var(--radius-full, 9999px)",
            background: "var(--surface-subtle, #f6f3f7)",
          }}
        >
          {(
            [
              { id: "all", label: `All (${items.length})` },
              { id: "web", label: "Web" },
              { id: "news", label: "News" },
              { id: "stock", label: "Stock" },
              { id: "generated", label: "Generated" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as MediaSourceCategory)}
              style={{
                padding: "3px 10px",
                borderRadius: "var(--radius-full, 9999px)",
                border: "none",
                background: activeTab === tab.id ? "var(--surface-card, #ffffff)" : "transparent",
                color: activeTab === tab.id ? "var(--accent-primary, #dc5f8b)" : "var(--text-tertiary, #847a83)",
                fontSize: 11,
                fontWeight: activeTab === tab.id ? 600 : 500,
                boxShadow: activeTab === tab.id ? "var(--shadow-sm)" : "none",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {selectedId && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              borderRadius: "var(--radius-full, 9999px)",
              background: "var(--accent-subtle, #fff2f6)",
              color: "var(--accent-primary, #dc5f8b)",
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            <CheckCircle2 size={12} />
            <span>Selected</span>
          </div>
        )}
      </div>

      {/* ── Grid of Image Cards ─────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: 10,
        }}
      >
        {filteredItems.map((item, idx) => {
          const isSelected = selectedId === item.id;
          const isHovered = hoveredId === item.id;

          return (
            <div
              key={item.id}
              onMouseEnter={() => setHoveredId(item.id)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => onSelect?.(item)}
              style={{
                position: "relative",
                borderRadius: "var(--radius-md, 12px)",
                overflow: "hidden",
                border: isSelected
                  ? "2px solid var(--accent-primary, #dc5f8b)"
                  : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                boxShadow: isSelected ? "var(--shadow-glow)" : "none",
                aspectRatio: "1/1",
                cursor: "pointer",
                background: "var(--surface-subtle, #f6f3f7)",
                transition: "transform 0.15s ease, box-shadow 0.15s ease",
                transform: isHovered ? "translateY(-2px)" : "none",
              }}
            >
              <img
                src={item.thumbnailUrl || item.url}
                alt={item.title}
                loading="lazy"
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  display: "block",
                }}
              />

              {/* Selection Badge */}
              {isSelected && (
                <div
                  style={{
                    position: "absolute",
                    top: 6,
                    right: 6,
                    background: "var(--accent-primary, #dc5f8b)",
                    color: "#ffffff",
                    borderRadius: "50%",
                    width: 20,
                    height: 20,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                  }}
                >
                  <CheckCircle2 size={13} />
                </div>
              )}

              {/* Source Tag Badge */}
              <div
                style={{
                  position: "absolute",
                  top: 6,
                  left: 6,
                  background: "rgba(0,0,0,0.55)",
                  backdropFilter: "blur(4px)",
                  color: "#ffffff",
                  fontSize: 9,
                  fontWeight: 600,
                  padding: "1px 6px",
                  borderRadius: "var(--radius-xs, 4px)",
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                {item.sourceCategory || "web"} #{idx + 1}
              </div>

              {/* Hover Action Bar */}
              {isHovered && (
                <div
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    right: 0,
                    padding: "6px 8px",
                    background: "linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 70%, transparent 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 4,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div style={{ display: "flex", gap: 4 }}>
                    {onUseAsReference && (
                      <button
                        type="button"
                        onClick={() => onUseAsReference(item)}
                        title="Use as Reference in Composer"
                        style={{
                          background: "rgba(255,255,255,0.2)",
                          border: "none",
                          borderRadius: 4,
                          padding: 4,
                          color: "#fff",
                          cursor: "pointer",
                        }}
                      >
                        <Bookmark size={12} />
                      </button>
                    )}
                    {onUpscale && (
                      <button
                        type="button"
                        onClick={() => onUpscale(item)}
                        title="Upscale / Enhance"
                        style={{
                          background: "rgba(255,255,255,0.2)",
                          border: "none",
                          borderRadius: 4,
                          padding: 4,
                          color: "#fff",
                          cursor: "pointer",
                        }}
                      >
                        <Sparkles size={12} />
                      </button>
                    )}
                  </div>

                  {onOpenSource && (
                    <button
                      type="button"
                      onClick={() => onOpenSource(item)}
                      title="Open Original Source"
                      style={{
                        background: "rgba(255,255,255,0.2)",
                        border: "none",
                        borderRadius: 4,
                        padding: 4,
                        color: "#fff",
                        cursor: "pointer",
                      }}
                    >
                      <ExternalLink size={12} />
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
