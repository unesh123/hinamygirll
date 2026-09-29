import React, { useState } from "react";
import {
  Brain,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Sparkles,
  Shield,
  Layers,
  Search,
} from "lucide-react";

interface DeepThinkingScratchpadProps {
  thought: string;
  isStreaming?: boolean;
  latencyMs?: number | null;
  sourcesCount?: number;
  defaultExpanded?: boolean;
}

export function DeepThinkingScratchpad({
  thought,
  isStreaming = false,
  latencyMs,
  sourcesCount = 0,
  defaultExpanded = false,
}: DeepThinkingScratchpadProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded || isStreaming);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  if (!thought && !isStreaming) return null;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(thought);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const wordCount = thought ? thought.trim().split(/\s+/).length : 0;
  const tokenEstimate = Math.round(wordCount * 1.3);

  return (
    <div
      style={{
        margin: "10px 0 14px 0",
        borderRadius: 10,
        backgroundColor: "#faf8f5", // Warm paper
        border: "1px solid #e8e3dc",
        overflow: "hidden",
        fontSize: 13,
        color: "#44403c",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {/* Header Bar */}
      <div
        onClick={() => setIsExpanded((prev) => !prev)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "9px 14px",
          cursor: "pointer",
          backgroundColor: isExpanded ? "#f5f3ef" : "#faf8f5",
          borderBottom: isExpanded ? "1px solid #e8e3dc" : "none",
          userSelect: "none",
          transition: "background-color 0.15s ease",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 22,
              height: 22,
              borderRadius: 6,
              backgroundColor: "#fbe1d1", // Warm peach accent
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#833d1c",
            }}
          >
            <Brain size={13} />
          </div>

          <span
            style={{
              fontFamily: "'Newsreader', 'Signifier', 'Georgia', serif",
              fontWeight: 600,
              fontSize: 14,
              color: "#1c1917",
            }}
          >
            Deep Thinking & Reasoning Scratchpad
          </span>

          {isStreaming ? (
            <span
              style={{
                fontSize: 11,
                color: "#d97706",
                backgroundColor: "#fef3c7",
                padding: "1px 6px",
                borderRadius: 4,
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <Sparkles size={11} style={{ animation: "spin 2s linear infinite" }} />
              Reasoning in progress…
            </span>
          ) : (
            <span style={{ fontSize: 11, color: "#78716c" }}>
              ({tokenEstimate} tokens ~ {wordCount} words)
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {latencyMs != null && (
            <span style={{ fontSize: 11, color: "#78716c" }}>
              {(latencyMs / 1000).toFixed(1)}s elapsed
            </span>
          )}

          {sourcesCount > 0 && (
            <span
              style={{
                fontSize: 11,
                backgroundColor: "#e0f2fe",
                color: "#0369a1",
                padding: "2px 6px",
                borderRadius: 4,
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: 3,
              }}
            >
              <Search size={10} />
              {sourcesCount} grounded {sourcesCount === 1 ? "source" : "sources"}
            </span>
          )}

          {thought && (
            <button
              type="button"
              onClick={handleCopy}
              title="Copy reasoning scratchpad"
              style={{
                background: "transparent",
                border: "none",
                color: "#78716c",
                cursor: "pointer",
                padding: 2,
                display: "flex",
                alignItems: "center",
              }}
            >
              {isCopied ? <Check size={13} color="#16a34a" /> : <Copy size={13} />}
            </button>
          )}

          {isExpanded ? <ChevronUp size={15} color="#78716c" /> : <ChevronDown size={15} color="#78716c" />}
        </div>
      </div>

      {/* Expanded Scratchpad Content */}
      {isExpanded && (
        <div
          style={{
            padding: "14px 18px",
            backgroundColor: "#ffffff",
            fontSize: 12.5,
            lineHeight: 1.6,
            color: "#292524",
            maxHeight: 450,
            overflowY: "auto",
            whiteSpace: "pre-wrap",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            borderTop: "1px solid #f5f3ef",
          }}
        >
          {thought || (
            <div style={{ color: "#a8a29e", fontStyle: "italic" }}>
              Synthesizing first-principles reasoning tree…
            </div>
          )}
        </div>
      )}
    </div>
  );
}
