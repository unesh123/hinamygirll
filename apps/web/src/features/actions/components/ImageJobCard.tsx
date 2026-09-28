import React, { useState, useEffect, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Wand2,
  CheckCircle2,
  Download,
  Copy,
  Check,
  Maximize2,
  AlertCircle,
  X,
} from "lucide-react";
import type { ImageJobFields } from "../types";

interface ImageJobCardProps {
  data: ImageJobFields;
  onCommit?: (updated: ImageJobFields) => void;
  compact?: boolean;
}

export function ImageJobCard({ data, onCommit, compact = false }: ImageJobCardProps) {
  // Extract all available image URLs
  const resolvedImages = useMemo(() => {
    if (Array.isArray(data.images) && data.images.length > 0) return data.images;
    if (data.resultUrl) return [data.resultUrl];
    if (data.thumbnailUrl) return [data.thumbnailUrl];
    return [];
  }, [data.images, data.resultUrl, data.thumbnailUrl]);

  const isComplete = Boolean(
    data.stage === "saved" || (resolvedImages.length > 0 && !data.isSearchFallback)
  );

  const [stage, setStage] = useState<"seeing" | "generating" | "saved" | "failed">(
    data.stage === "failed" ? "failed" : isComplete ? "saved" : (data.stage || "generating")
  );
  const [elapsedSeconds, setElapsedSeconds] = useState(data.elapsedSeconds || 0);
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  // Sync state when data props update
  useEffect(() => {
    if (data.stage === "failed") {
      setStage("failed");
    } else if (isComplete || data.stage === "saved") {
      setStage("saved");
    } else if (data.stage) {
      setStage(data.stage);
    }
  }, [data.stage, isComplete]);

  // Elapsed seconds timer during generation
  useEffect(() => {
    if (stage === "saved" || stage === "failed" || data.isSearchFallback) return;
    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [stage, data.isSearchFallback]);

  // Close lightbox on Escape key
  useEffect(() => {
    if (!lightboxOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [lightboxOpen]);

  const handleCopyPrompt = useCallback(() => {
    if (!data.prompt) return;
    navigator.clipboard.writeText(data.prompt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [data.prompt]);

  const handleDownload = useCallback(async (url: string, index: number) => {
    if (!url) return;
    setIsDownloading(true);
    try {
      const slug = (data.prompt || "image")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .slice(0, 40);
      const prefix = (data.model || "seedance").toLowerCase().replace(/[^a-z0-9]+/g, "-");
      const filename = `hina-${prefix}-${slug}-${index + 1}.png`;

      const res = await fetch(url);
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch {
      const a = document.createElement("a");
      a.href = url;
      a.download = `hina-image-${index + 1}.png`;
      a.target = "_blank";
      a.click();
    } finally {
      setIsDownloading(false);
      onCommit?.({ ...data, stage: "saved", elapsedSeconds });
    }
  }, [data, elapsedSeconds, onCommit]);

  return (
    <>
      <div
        style={{
          padding: compact ? "12px 14px" : "18px 20px",
          borderRadius: "16px",
          background: "var(--bg-surface-raised, #ffffff)",
          border: "1px solid var(--border-default, #e2e8f0)",
          boxShadow: "0 10px 30px -5px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04)",
          color: "var(--text-primary, #0f172a)",
          display: "flex",
          flexDirection: "column",
          gap: "14px",
          width: "100%",
          maxWidth: 540,
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 10,
                background: "linear-gradient(135deg, rgba(244, 114, 182, 0.2), rgba(168, 85, 247, 0.2))",
                color: "#db2777",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 2px 8px rgba(219, 39, 119, 0.15)",
                flexShrink: 0,
              }}
            >
              <Sparkles size={16} />
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "0.88rem", fontWeight: 750, color: "var(--text-primary, #0f172a)", letterSpacing: "-0.01em" }}>
                Image Generation Object
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                <span
                  style={{
                    fontSize: "0.68rem",
                    fontWeight: 650,
                    color: "#9333ea",
                    background: "rgba(147, 51, 234, 0.08)",
                    padding: "1px 6px",
                    borderRadius: 4,
                    border: "1px solid rgba(147, 51, 234, 0.18)",
                  }}
                >
                  {data.model || "✨ Seedance 5.0"}
                </span>
                <span
                  style={{
                    fontSize: "0.68rem",
                    fontWeight: 600,
                    color: "var(--text-tertiary, #64748b)",
                    background: "var(--surface-subtle, rgba(0,0,0,0.04))",
                    padding: "1px 6px",
                    borderRadius: 4,
                  }}
                >
                  {data.resolution || "1024 × 1024"}
                </span>
              </div>
            </div>
          </div>

          {/* Status Badge */}
          <span
            style={{
              fontSize: "0.75rem",
              color: data.isSearchFallback
                ? "#b45309"
                : stage === "saved"
                  ? "#059669"
                  : stage === "failed"
                    ? "#dc2626"
                    : "#db2777",
              fontWeight: 700,
              background: data.isSearchFallback
                ? "rgba(245, 158, 11, 0.1)"
                : stage === "saved"
                  ? "rgba(16, 185, 129, 0.1)"
                  : stage === "failed"
                    ? "rgba(239, 68, 68, 0.1)"
                    : "rgba(244, 114, 182, 0.1)",
              border: `1px solid ${
                data.isSearchFallback
                  ? "rgba(245, 158, 11, 0.25)"
                  : stage === "saved"
                    ? "rgba(16, 185, 129, 0.25)"
                    : stage === "failed"
                      ? "rgba(239, 68, 68, 0.25)"
                      : "rgba(244, 114, 182, 0.25)"
              }`,
              padding: "3px 10px",
              borderRadius: 999,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {stage === "generating" && !data.isSearchFallback && (
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#db2777",
                }}
              />
            )}
            {stage === "saved" && <CheckCircle2 size={13} color="#059669" />}
            {data.isSearchFallback
              ? "Search only — generation did not run"
              : stage === "saved"
                ? "Completed"
                : stage === "failed"
                  ? "Generation Failed"
                  : `Generating · ${elapsedSeconds}s`}
          </span>
        </div>

        {/* Fallback Banner if web search ran instead */}
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

        {/* Prompt Bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
            background: "var(--surface-subtle, rgba(0,0,0,0.03))",
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid var(--border-subtle, rgba(0,0,0,0.06))",
          }}
        >
          <span
            style={{
              fontSize: "0.84rem",
              fontWeight: 600,
              color: "var(--text-primary, #0f172a)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
            }}
            title={data.prompt}
          >
            {data.prompt}
          </span>
          <button
            type="button"
            onClick={handleCopyPrompt}
            title="Copy prompt"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px 6px",
              borderRadius: 6,
              color: copied ? "#059669" : "var(--text-tertiary, #94a3b8)",
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: "0.72rem",
              fontWeight: 600,
              transition: "all 0.15s ease",
            }}
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>

        {/* Latent Diffusion Synthesis Canvas (Generating State) */}
        {stage === "generating" && !data.isSearchFallback && (
          <div
            style={{
              position: "relative",
              width: "100%",
              aspectRatio: "1 / 1",
              maxHeight: 340,
              borderRadius: 14,
              overflow: "hidden",
              background: "var(--canvas-bg, #0b0f19)",
              border: "1px solid var(--border-subtle, rgba(255,255,255,0.1))",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "inset 0 0 40px rgba(0,0,0,0.5)",
            }}
          >
            {/* Animated Radial Latent Wave */}
            <motion.div
              animate={{
                scale: [1, 1.15, 1],
                rotate: [0, 180, 360],
                opacity: [0.35, 0.65, 0.35],
              }}
              transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
              style={{
                position: "absolute",
                width: "160%",
                height: "160%",
                backgroundImage:
                  "radial-gradient(circle at 35% 35%, rgba(236, 72, 153, 0.5) 0%, transparent 50%), radial-gradient(circle at 65% 65%, rgba(99, 102, 241, 0.5) 0%, transparent 50%), radial-gradient(circle at 50% 50%, rgba(14, 165, 233, 0.35) 0%, transparent 65%)",
                filter: "blur(32px)",
                pointerEvents: "none",
              }}
            />

            {/* Shimmer Scanline */}
            <motion.div
              animate={{ x: ["-100%", "200%"] }}
              transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
              style={{
                position: "absolute",
                inset: 0,
                background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent)",
                pointerEvents: "none",
              }}
            />

            {/* Center Latent Core */}
            <div
              style={{
                position: "relative",
                zIndex: 2,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 14,
                padding: "0 24px",
                textAlign: "center",
              }}
            >
              {/* Spinning Glow Ring */}
              <div style={{ position: "relative", width: 56, height: 56 }}>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: "50%",
                    background: "radial-gradient(circle, rgba(236, 72, 153, 0.45) 0%, transparent 70%)",
                    filter: "blur(8px)",
                  }}
                />
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: "50%",
                    border: "2.5px solid rgba(244, 114, 182, 0.2)",
                    borderTopColor: "#ec4899",
                    borderRightColor: "#a855f7",
                    animation: "spin 1.2s cubic-bezier(0.5, 0.1, 0.5, 0.9) infinite",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#ffffff",
                  }}
                >
                  <Wand2 size={20} />
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: "0.86rem", fontWeight: 700, color: "#ffffff", letterSpacing: "0.01em" }}>
                  {data.model ? `Synthesizing ${data.model}` : "Synthesizing Seedance 5.0 Visuals"}
                </span>
                <span style={{ fontSize: "0.72rem", color: "rgba(255, 255, 255, 0.65)", fontWeight: 500 }}>
                  High-res 1024×1024 · Ultra High Fidelity
                </span>
              </div>

              {/* Denoising Progress Dots */}
              <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
                {[0, 1, 2, 3].map((i) => (
                  <motion.div
                    key={i}
                    animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: "#ec4899",
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Failed State */}
        {stage === "failed" && (
          <div
            style={{
              padding: "16px",
              borderRadius: 12,
              background: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              display: "flex",
              alignItems: "center",
              gap: 12,
              color: "#b91c1c",
            }}
          >
            <AlertCircle size={20} />
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>Generation could not complete</span>
              <span style={{ fontSize: "0.76rem", color: "#991b1b" }}>
                {data.note || "The image generation service encountered an unexpected error. Please retry."}
              </span>
            </div>
          </div>
        )}

        {/* Completed Artwork Display */}
        {stage === "saved" && resolvedImages.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {resolvedImages.length === 1 ? (
              /* Single Hero Artwork */
              <div
                style={{
                  position: "relative",
                  width: "100%",
                  borderRadius: 14,
                  overflow: "hidden",
                  border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.06)",
                  cursor: "pointer",
                  background: "var(--surface-subtle, #f8fafc)",
                }}
                onClick={() => {
                  setActiveImageIndex(0);
                  setLightboxOpen(true);
                }}
              >
                <img
                  src={resolvedImages[0]}
                  alt={data.prompt}
                  style={{
                    width: "100%",
                    height: "auto",
                    maxHeight: 460,
                    objectFit: "contain",
                    display: "block",
                  }}
                  loading="lazy"
                />
                {/* Hover Quick Action Scrim */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: "linear-gradient(to top, rgba(0,0,0,0.65) 0%, transparent 40%, rgba(0,0,0,0.2) 100%)",
                    opacity: 0,
                    transition: "opacity 0.2s ease",
                    display: "flex",
                    alignItems: "flex-end",
                    justifyContent: "space-between",
                    padding: 12,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = "0")}
                >
                  <span style={{ fontSize: "0.75rem", color: "#ffffff", fontWeight: 600 }}>
                    Click to inspect full resolution
                  </span>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownload(resolvedImages[0], 0);
                      }}
                      style={{
                        background: "rgba(255,255,255,0.92)",
                        border: "none",
                        borderRadius: 6,
                        padding: "6px 10px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        color: "#0f172a",
                      }}
                    >
                      <Download size={13} />
                      <span>Download</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveImageIndex(0);
                        setLightboxOpen(true);
                      }}
                      style={{
                        background: "rgba(255,255,255,0.92)",
                        border: "none",
                        borderRadius: 6,
                        padding: "6px 8px",
                        cursor: "pointer",
                        color: "#0f172a",
                      }}
                    >
                      <Maximize2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* Multi-Image Grid */
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: resolvedImages.length === 2 ? "1fr 1fr" : "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: 8,
                }}
              >
                {resolvedImages.map((imgUrl, idx) => (
                  <div
                    key={idx}
                    style={{
                      position: "relative",
                      borderRadius: 10,
                      overflow: "hidden",
                      aspectRatio: "1 / 1",
                      border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                      cursor: "pointer",
                      background: "var(--surface-subtle, #f8fafc)",
                    }}
                    onClick={() => {
                      setActiveImageIndex(idx);
                      setLightboxOpen(true);
                    }}
                  >
                    <img
                      src={imgUrl}
                      alt={`${data.prompt} - ${idx + 1}`}
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      loading="lazy"
                    />
                    <div
                      style={{
                        position: "absolute",
                        inset: 0,
                        background: "rgba(0,0,0,0.4)",
                        opacity: 0,
                        transition: "opacity 0.2s ease",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 8,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                      onMouseLeave={(e) => (e.currentTarget.style.opacity = "0")}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownload(imgUrl, idx);
                        }}
                        style={{
                          background: "#ffffff",
                          border: "none",
                          borderRadius: 6,
                          padding: 6,
                          cursor: "pointer",
                          color: "#0f172a",
                        }}
                        title="Download image"
                      >
                        <Download size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveImageIndex(idx);
                          setLightboxOpen(true);
                        }}
                        style={{
                          background: "#ffffff",
                          border: "none",
                          borderRadius: 6,
                          padding: 6,
                          cursor: "pointer",
                          color: "#0f172a",
                        }}
                        title="View full resolution"
                      >
                        <Maximize2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Quick Action Footer */}
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              <button
                type="button"
                onClick={() => handleDownload(resolvedImages[activeImageIndex] || resolvedImages[0], activeImageIndex)}
                disabled={isDownloading}
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  padding: "9px 16px",
                  borderRadius: 9,
                  background: "linear-gradient(135deg, #059669, #10b981)",
                  color: "#ffffff",
                  border: "none",
                  fontWeight: 750,
                  fontSize: "0.84rem",
                  cursor: isDownloading ? "wait" : "pointer",
                  boxShadow: "0 2px 8px rgba(16, 185, 129, 0.25)",
                  transition: "opacity 0.15s ease",
                }}
              >
                <Download size={15} />
                <span>{isDownloading ? "Saving..." : "Download HD Image"}</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveImageIndex(0);
                  setLightboxOpen(true);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  padding: "9px 14px",
                  borderRadius: 9,
                  background: "var(--surface-subtle, rgba(0,0,0,0.04))",
                  color: "var(--text-primary, #0f172a)",
                  border: "1px solid var(--border-default, #e2e8f0)",
                  fontWeight: 650,
                  fontSize: "0.82rem",
                  cursor: "pointer",
                }}
              >
                <Maximize2 size={14} />
                <span>Full View</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Fullscreen Lightbox Modal */}
      <AnimatePresence>
        {lightboxOpen && resolvedImages[activeImageIndex] && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 99999,
              background: "rgba(0, 0, 0, 0.92)",
              backdropFilter: "blur(16px)",
              display: "flex",
              flexDirection: "column",
            }}
            onClick={() => setLightboxOpen(false)}
          >
            {/* Top Bar */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 24px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
                color: "#ffffff",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: "rgba(244, 114, 182, 0.2)",
                    color: "#f472b6",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Sparkles size={16} />
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: "0.95rem", fontWeight: 700 }}>
                    {data.prompt}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.6)" }}>
                    {data.model || "Seedance 5.0"} · {data.resolution || "1024 × 1024 PNG"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <button
                  type="button"
                  onClick={() => handleDownload(resolvedImages[activeImageIndex], activeImageIndex)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "8px 14px",
                    borderRadius: 8,
                    background: "#059669",
                    color: "#ffffff",
                    border: "none",
                    fontWeight: 700,
                    fontSize: "0.82rem",
                    cursor: "pointer",
                  }}
                >
                  <Download size={14} />
                  <span>Download HD</span>
                </button>
                <button
                  type="button"
                  onClick={() => setLightboxOpen(false)}
                  style={{
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "none",
                    borderRadius: 8,
                    padding: 8,
                    color: "#ffffff",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                  title="Close (Esc)"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Image Stage */}
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 24,
                overflow: "auto",
              }}
              onClick={() => setLightboxOpen(false)}
            >
              <motion.img
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                src={resolvedImages[activeImageIndex]}
                alt={data.prompt}
                onClick={(e) => e.stopPropagation()}
                style={{
                  maxWidth: "90vw",
                  maxHeight: "82vh",
                  objectFit: "contain",
                  borderRadius: 12,
                  boxShadow: "0 20px 50px rgba(0,0,0,0.5)",
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
