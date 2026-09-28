import React, { useState, useEffect, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, ChevronDown, ChevronUp, Globe, ExternalLink, Sparkles, Search } from "lucide-react";

export interface BrainSource {
  id: string;
  title: string;
  url?: string;
  domain?: string;
  snippet?: string;
}

export interface HinaBrainThinkingProps {
  thought?: string;
  sources?: BrainSource[];
  isLive?: boolean;
  isSearching?: boolean;
  searchQuery?: string;
  latencyMs?: number | null;
  defaultExpanded?: boolean;
}

const PROGRESSIVE_STAGES = [
  "Decomposing problem & identifying constraints...",
  "Retrieving neural memory & context...",
  "Evaluating architectural trade-offs & edge cases...",
  "Synthesizing high-signal reasoned answer...",
];

export const HinaBrainThinking: React.FC<HinaBrainThinkingProps> = memo(
  ({
    thought,
    sources = [],
    isLive = false,
    isSearching = false,
    searchQuery,
    latencyMs,
    defaultExpanded = false,
  }) => {
    // If not live and has neither thought nor sources, don't render anything
    const hasContent = Boolean((thought && thought.trim().length > 0) || sources.length > 0);
    if (!isLive && !hasContent) {
      return null;
    }

    const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded || isLive);
    const [stageIndex, setStageIndex] = useState(0);

    useEffect(() => {
      if (!isLive) return;
      const interval = window.setInterval(() => {
        setStageIndex((prev) => (prev + 1) % PROGRESSIVE_STAGES.length);
      }, 2200);
      return () => window.clearInterval(interval);
    }, [isLive]);

    // Format duration string if latencyMs is present
    const durationLabel = latencyMs
      ? `${(latencyMs / 1000).toFixed(1)}s`
      : null;

    const sourcesCount = sources.length;
    const currentStageText = isSearching
      ? `Hina is searching web: ${searchQuery || "information"}...`
      : PROGRESSIVE_STAGES[stageIndex];

    return (
      <div
        className="hina-brain-thinking"
        style={{
          margin: "6px 0 12px 0",
          borderRadius: 12,
          background: isLive
            ? "linear-gradient(135deg, rgba(236, 72, 153, 0.12), rgba(99, 102, 241, 0.08))"
            : "var(--surface-card, #ffffff)",
          border: isLive
            ? "1px solid var(--border-accent, rgba(236, 72, 153, 0.4))"
            : "1px solid var(--border-subtle, rgba(0, 0, 0, 0.1))",
          boxShadow: isLive
            ? "0 2px 14px -2px rgba(236, 72, 153, 0.25)"
            : "0 1px 3px rgba(0, 0, 0, 0.05)",
          overflow: "hidden",
          transition: "all 0.25s ease",
        }}
      >
        {/* Header / Brain Status Toggle */}
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            background: "none",
            border: "none",
            color: "inherit",
            cursor: "pointer",
            textAlign: "left",
            userSelect: "none",
          }}
          aria-expanded={isExpanded}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: 6,
                background: isLive
                  ? "linear-gradient(135deg, #ec4899, #8b5cf6)"
                  : "linear-gradient(135deg, rgba(236, 72, 153, 0.2), rgba(99, 102, 241, 0.15))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: isLive ? "#ffffff" : "#ec4899",
                boxShadow: isLive ? "0 0 10px rgba(236, 72, 153, 0.5)" : "none",
              }}
            >
              {isSearching ? (
                <Search size={12} className={isLive ? "animate-pulse" : ""} />
              ) : isLive ? (
                <Sparkles size={12} className="animate-spin" />
              ) : (
                <Brain size={12} color="#ec4899" />
              )}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 650,
                  letterSpacing: "0.01em",
                  color: isLive ? "#db2777" : "var(--text-primary, #1e191d)",
                }}
              >
                {isSearching
                  ? `Hina is searching web: ${searchQuery || "information"}...`
                  : isLive
                  ? "Hina is thinking & synthesizing..."
                  : "Thought Process & Brain Synthesis"}
              </span>

              {/* Status Pills */}
              {!isLive && (
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  {sourcesCount > 0 && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        padding: "1px 6px",
                        borderRadius: 10,
                        background: "rgba(236, 72, 153, 0.12)",
                        color: "#db2777",
                        border: "1px solid rgba(236, 72, 153, 0.25)",
                      }}
                    >
                      {sourcesCount} {sourcesCount === 1 ? "source" : "sources"} integrated
                    </span>
                  )}
                  {durationLabel && (
                    <span
                      style={{
                        fontSize: 10,
                        padding: "1px 6px",
                        borderRadius: 10,
                        background: "var(--surface-subtle, rgba(0, 0, 0, 0.05))",
                        color: "var(--text-secondary, #64748b)",
                        border: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.06))",
                      }}
                    >
                      {durationLabel}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div
            style={{
              color: "var(--text-tertiary, #64748b)",
              display: "flex",
              alignItems: "center",
            }}
          >
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </button>

        {/* Expandable Mind / Grounded Knowledge Content */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              style={{
                borderTop: isLive
                  ? "1px solid rgba(236, 72, 153, 0.2)"
                  : "1px solid var(--border-subtle, rgba(0, 0, 0, 0.08))",
                padding: "10px 14px",
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              {/* Integrated Knowledge Sources (Not external pop-pop cards) */}
              {sources.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    padding: "8px 10px",
                    borderRadius: 8,
                    background: "var(--surface-subtle, rgba(0, 0, 0, 0.03))",
                    border: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.08))",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      fontSize: 11,
                      fontWeight: 700,
                      color: "#db2777",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    <Globe size={11} color="#db2777" />
                    <span>Grounded Knowledge Base ({sources.length})</span>
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                      gap: 6,
                      marginTop: 2,
                    }}
                  >
                    {sources.map((src, i) => {
                      let parsedDomain = src.domain || "Web Source";
                      if (src.url) {
                        try {
                          parsedDomain = new URL(src.url).hostname.replace(/^www\./, "");
                        } catch {}
                      }
                      const faviconUrl = parsedDomain && parsedDomain !== "Web Source"
                        ? `https://www.google.com/s2/favicons?domain=${parsedDomain}&sz=32`
                        : null;

                      return (
                        <a
                          key={src.id || i}
                          href={src.url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={src.title || src.snippet}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 8,
                            padding: "6px 10px",
                            borderRadius: 6,
                            background: "var(--surface-card, #ffffff)",
                            border: "1px solid var(--border-default, rgba(0, 0, 0, 0.1))",
                            textDecoration: "none",
                            color: "var(--text-primary, #1e191d)",
                            fontSize: 11.5,
                            boxShadow: "0 1px 2px rgba(0, 0, 0, 0.04)",
                            transition: "background 0.15s, border-color 0.15s, box-shadow 0.15s",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = "var(--accent-subtle, rgba(236, 72, 153, 0.08))";
                            e.currentTarget.style.borderColor = "rgba(236, 72, 153, 0.4)";
                            e.currentTarget.style.boxShadow = "0 2px 6px rgba(236, 72, 153, 0.15)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = "var(--surface-card, #ffffff)";
                            e.currentTarget.style.borderColor = "var(--border-default, rgba(0, 0, 0, 0.1))";
                            e.currentTarget.style.boxShadow = "0 1px 2px rgba(0, 0, 0, 0.04)";
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
                            {faviconUrl ? (
                              <img
                                src={faviconUrl}
                                alt=""
                                style={{ width: 14, height: 14, borderRadius: 2, flexShrink: 0 }}
                                onError={(e) => {
                                  e.currentTarget.style.display = "none";
                                }}
                              />
                            ) : (
                              <Globe size={12} style={{ color: "#ec4899", flexShrink: 0 }} />
                            )}
                            <span
                              style={{
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                fontWeight: 600,
                                color: "var(--text-primary, #1e191d)",
                              }}
                            >
                              [{i + 1}] {parsedDomain}
                            </span>
                          </div>
                          <ExternalLink size={11} style={{ opacity: 0.5, flexShrink: 0 }} />
                        </a>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Thought Stream / Internal Reasoning */}
              {thought && (
                <div
                  style={{
                    fontSize: 12,
                    lineHeight: 1.6,
                    color: "var(--text-secondary, #334155)",
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    maxHeight: 280,
                    overflowY: "auto",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "var(--surface-subtle, rgba(0, 0, 0, 0.02))",
                    border: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.06))",
                  }}
                >
                  {thought}
                  {isLive && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 6,
                        height: 13,
                        background: "#ec4899",
                        marginLeft: 4,
                        verticalAlign: "middle",
                        borderRadius: 1,
                      }}
                      className="animate-pulse"
                    />
                  )}
                </div>
              )}

              {isLive && !thought && !sources.length && (
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--text-secondary, #475569)",
                    fontStyle: "italic",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "4px 2px",
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: "#ec4899",
                      display: "inline-block",
                      boxShadow: "0 0 8px #ec4899",
                    }}
                    className="animate-ping"
                  />
                  <span>{isSearching ? "Querying real-time search index & evidence..." : currentStageText}</span>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }
);
