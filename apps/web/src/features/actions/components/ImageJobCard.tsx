import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ImageIcon, Eye, Wand2, CheckCircle2, Download } from "lucide-react";
import { HINA_MOTION } from "../../motion/MOTION";
import type { ImageJobFields } from "../types";

interface ImageJobCardProps {
  data: ImageJobFields;
  onCommit?: (updated: ImageJobFields) => void;
  compact?: boolean;
}

export function ImageJobCard({ data, onCommit, compact = false }: ImageJobCardProps) {
  const [stage, setStage] = useState<"seeing" | "generating" | "saved">(data.stage || "seeing");
  const [percent, setPercent] = useState(data.progressPercent || 30);

  useEffect(() => {
    if (stage === "seeing") {
      const t = setTimeout(() => {
        setStage("generating");
        setPercent(65);
      }, 1600);
      return () => clearTimeout(t);
    }
    if (stage === "generating") {
      const t = setTimeout(() => {
        setStage("saved");
        setPercent(100);
      }, 2000);
      return () => clearTimeout(t);
    }
  }, [stage]);

  return (
    <div
      style={{
        padding: compact ? "12px 14px" : "16px 20px",
        borderRadius: "14px",
        background: "var(--bg-surface-raised, #18202a)",
        border: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
        boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
        color: "#ffffff",
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
              background: "rgba(243, 111, 156, 0.15)",
              color: "#f36f9c",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ImageIcon size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>Image Generation Studio</span>
        </div>
        <span style={{ fontSize: "0.75rem", color: "#f36f9c", fontWeight: 650 }}>
          {percent}%
        </span>
      </div>

      {/* Main card body with locked thumbnail */}
      <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
        {/* Thumbnail anchor */}
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: 10,
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            overflow: "hidden",
            position: "relative",
          }}
        >
          {data.thumbnailUrl ? (
            <img
              src={data.thumbnailUrl}
              alt="Thumbnail"
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <div style={{ color: "rgba(255,255,255,0.3)" }}>
              <ImageIcon size={28} />
            </div>
          )}
          {stage !== "saved" && (
            <motion.div
              animate={{ opacity: [0.3, 0.7, 0.3] }}
              transition={{ duration: 1.5, repeat: Infinity }}
              style={{
                position: "absolute",
                inset: 0,
                background: "linear-gradient(45deg, transparent, rgba(243, 111, 156, 0.15), transparent)",
              }}
            />
          )}
        </div>

        {/* Stages Walk: Seeing -> Generating -> Saved */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
          <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#ffffff" }}>
            {data.prompt.slice(0, 50)}...
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {/* Stage 1: Seeing */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem" }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: stage === "seeing" ? "#f36f9c" : "#10b981",
                  boxShadow: stage === "seeing" ? "0 0 8px #f36f9c" : "none",
                }}
              />
              <span style={{ color: stage === "seeing" ? "#ffffff" : "rgba(255,255,255,0.5)" }}>
                Seeing & Parsing Intent…
              </span>
            </div>

            {/* Stage 2: Generating */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem" }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: stage === "generating" ? "#f36f9c" : stage === "saved" ? "#10b981" : "rgba(255,255,255,0.2)",
                  boxShadow: stage === "generating" ? "0 0 8px #f36f9c" : "none",
                }}
              />
              <span style={{ color: stage === "generating" ? "#ffffff" : "rgba(255,255,255,0.5)" }}>
                Generating with Multimodal Model…
              </span>
            </div>

            {/* Stage 3: Saved */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem" }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: stage === "saved" ? "#10b981" : "rgba(255,255,255,0.2)",
                  boxShadow: stage === "saved" ? "0 0 8px #10b981" : "none",
                }}
              />
              <span style={{ color: stage === "saved" ? "#10b981" : "rgba(255,255,255,0.5)", fontWeight: stage === "saved" ? 650 : 400 }}>
                Saved to Artifacts
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Action / Download button */}
      {stage === "saved" && (
        <motion.button
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          type="button"
          onClick={() => onCommit?.({ ...data, stage, progressPercent: 100 })}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            background: "#10b981",
            color: "#000000",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Download size={14} />
          <span>Save Image Result ↵</span>
        </motion.button>
      )}
    </div>
  );
}
