import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ImageIcon, Wand2, CheckCircle2, Download, RefreshCw, AlertCircle } from "lucide-react";
import type { ImageJobFields } from "../types";

interface ImageJobCardProps {
  data: ImageJobFields;
  onCommit?: (updated: ImageJobFields) => void;
  compact?: boolean;
}

export function ImageJobCard({ data, onCommit, compact = false }: ImageJobCardProps) {
  const [stage, setStage] = useState<"seeing" | "generating" | "saved">(data.stage || "generating");
  const [elapsedSeconds, setElapsedSeconds] = useState(data.elapsedSeconds || 0);

  // Honest elapsed seconds timer (No fake percentages)
  useEffect(() => {
    if (stage === "saved" || data.isSearchFallback) return;
    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [stage, data.isSearchFallback]);

  return (
    <div
      style={{
        padding: compact ? "12px 14px" : "16px 20px",
        borderRadius: "14px",
        background: "var(--bg-surface-raised, #ffffff)",
        border: "1px solid var(--border-default, #e2e8f0)",
        boxShadow: "0 8px 30px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04)",
        color: "var(--text-primary, #0f172a)",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        width: "100%",
        maxWidth: 520,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: "rgba(244, 114, 182, 0.15)",
              color: "#db2777",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ImageIcon size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>
            Image Generation Object
          </span>
        </div>
        <span
          style={{
            fontSize: "0.75rem",
            color: data.isSearchFallback ? "#b45309" : stage === "saved" ? "#059669" : "#db2777",
            fontWeight: 700,
            background: data.isSearchFallback ? "rgba(245, 158, 11, 0.1)" : "rgba(244, 114, 182, 0.1)",
            padding: "2px 8px",
            borderRadius: 6,
          }}
        >
          {data.isSearchFallback
            ? "Search only — generation did not run"
            : stage === "saved"
              ? "Completed"
              : `Generating · ${elapsedSeconds}s`}
        </span>
      </div>

      {/* Honest fallback banner if search ran instead of generation */}
      {data.isSearchFallback && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(245, 158, 11, 0.1)",
            border: "1px solid rgba(245, 158, 11, 0.3)",
            fontSize: "0.78rem",
            color: "#92400e",
            fontWeight: 600,
          }}
        >
          <AlertCircle size={15} color="#d97706" />
          <span>Search only — generation did not run. Public web images were returned.</span>
        </div>
      )}

      {/* Main card body with stable thumbnail canvas */}
      <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
        {/* Thumbnail anchor */}
        <div
          style={{
            width: 76,
            height: 76,
            borderRadius: 10,
            background: "var(--surface-subtle, rgba(0,0,0,0.04))",
            border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            overflow: "hidden",
            position: "relative",
          }}
        >
          {data.thumbnailUrl || data.resultUrl ? (
            <img
              src={data.thumbnailUrl || data.resultUrl}
              alt="Generated Art"
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <div style={{ color: "var(--text-tertiary, #94a3b8)", display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <ImageIcon size={26} />
              <span style={{ fontSize: "0.65rem", fontWeight: 600 }}>16:9 Canvas</span>
            </div>
          )}
          {stage === "generating" && !data.thumbnailUrl && (
            <motion.div
              animate={{ opacity: [0.3, 0.7, 0.3] }}
              transition={{ duration: 1.5, repeat: Infinity }}
              style={{
                position: "absolute",
                inset: 0,
                background: "linear-gradient(45deg, transparent, rgba(244, 114, 182, 0.15), transparent)",
              }}
            />
          )}
        </div>

        {/* Stages Walk: Seeing -> Generating -> Saved */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: "0.95rem",
              fontWeight: 700,
              color: "var(--text-primary, #0f172a)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {data.prompt}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {/* Stage 1: Preparing */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem" }}>
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: stage === "seeing" ? "#db2777" : "#059669",
                }}
              />
              <span style={{ color: stage === "seeing" ? "var(--text-primary, #0f172a)" : "var(--text-secondary, #64748b)", fontWeight: stage === "seeing" ? 700 : 500 }}>
                Preparing request & prompt parsing
              </span>
            </div>

            {/* Stage 2: Generating */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem" }}>
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: stage === "generating" ? "#db2777" : stage === "saved" ? "#059669" : "#94a3b8",
                  boxShadow: stage === "generating" ? "0 0 6px #db2777" : "none",
                }}
              />
              <span style={{ color: stage === "generating" ? "var(--text-primary, #0f172a)" : "var(--text-secondary, #64748b)", fontWeight: stage === "generating" ? 700 : 500 }}>
                {stage === "generating" ? `Generating with Multimodal Model · ${elapsedSeconds}s` : "Model generation"}
              </span>
            </div>

            {/* Stage 3: Saved */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem" }}>
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: stage === "saved" ? "#059669" : "#cbd5e1",
                }}
              />
              <span style={{ color: stage === "saved" ? "#059669" : "var(--text-secondary, #64748b)", fontWeight: stage === "saved" ? 700 : 500 }}>
                Saved to Artifacts
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Result actions */}
      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        {stage === "saved" ? (
          <button
            type="button"
            onClick={() => onCommit?.({ ...data, stage: "saved", elapsedSeconds })}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "9px 14px",
              borderRadius: 8,
              background: "#059669",
              color: "#ffffff",
              border: "none",
              fontWeight: 750,
              fontSize: "0.84rem",
              cursor: "pointer",
            }}
          >
            <Download size={15} />
            <span>Download Artifact</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setStage("saved")}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "8px 12px",
              borderRadius: 8,
              background: "var(--surface-subtle, rgba(0,0,0,0.04))",
              color: "var(--text-primary, #0f172a)",
              border: "1px solid var(--border-default, #e2e8f0)",
              fontWeight: 650,
              fontSize: "0.8rem",
              cursor: "pointer",
            }}
          >
            <CheckCircle2 size={14} color="#059669" />
            <span>Simulate Finish</span>
          </button>
        )}
      </div>
    </div>
  );
}

