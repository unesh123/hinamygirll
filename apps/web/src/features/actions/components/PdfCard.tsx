import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { FileText, Download, Check, Sparkles, Loader2 } from "lucide-react";
import { HINA_MOTION } from "../../motion/MOTION";
import { downloadMarkdownPdf } from "../../documents/exportPdf";
import type { PdfDocFields } from "../types";

interface PdfCardProps {
  data: PdfDocFields;
  onCommit?: (updated: PdfDocFields) => void;
  compact?: boolean;
}

export function PdfCard({ data, onCommit, compact = false }: PdfCardProps) {
  const [visibleCount, setVisibleCount] = useState(data.outline.length);
  const [isReady, setIsReady] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    setVisibleCount(data.outline.length);
    setIsReady(true);
  }, [data.outline.length]);

  const handleDownload = async () => {
    try {
      setDownloading(true);
      const title = data.title || "Document";
      const docMarkdown =
        `# ${title}\n\n## Overview\n\nExecutive documentation compiled by Hinaa Academic Studio.\n\n` +
        data.outline
          .map(
            (o) =>
              `### ${o}\n\nComprehensive technical documentation and analysis regarding ${o}.\n`,
          )
          .join("\n");
      await downloadMarkdownPdf(title, docMarkdown);
      onCommit?.({ ...data, stage: "ready" });
    } catch (e) {
      console.error("PDF download failed:", e);
      onCommit?.({ ...data, stage: "ready" });
    } finally {
      setDownloading(false);
    }
  };

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
              background: "rgba(239, 68, 68, 0.15)",
              color: "#ef4444",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <FileText size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>
            {data.title || "PDF Document"}
          </span>
        </div>
        <span
          style={{
            fontSize: "0.72rem",
            padding: "2px 8px",
            borderRadius: 4,
            background: isReady ? "rgba(16, 185, 129, 0.15)" : "rgba(255,255,255,0.06)",
            color: isReady ? "#10b981" : "rgba(255,255,255,0.6)",
            fontWeight: 650,
          }}
        >
          {isReady ? "Document Ready" : "Composing Outline…"}
        </span>
      </div>

      {/* Outlines */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          padding: "10px 14px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
        }}
      >
        {data.outline.slice(0, visibleCount).map((item, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              fontSize: "0.82rem",
              color: "rgba(255,255,255,0.85)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span style={{ color: "#ef4444", fontWeight: 700 }}>›</span>
            <span>{item}</span>
          </motion.div>
        ))}
      </div>

      {/* Download chip */}
      <motion.button
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={HINA_MOTION.spring}
        type="button"
        disabled={downloading}
        onClick={handleDownload}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          padding: "8px 14px",
          borderRadius: 8,
          background: "#ef4444",
          color: "#ffffff",
          border: "none",
          fontWeight: 700,
          fontSize: "0.82rem",
          cursor: downloading ? "wait" : "pointer",
          marginTop: 4,
          opacity: downloading ? 0.8 : 1,
        }}
      >
        {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
        <span>{downloading ? "Compiling PDF…" : "Download PDF ↵"}</span>
      </motion.button>
    </div>
  );
}
