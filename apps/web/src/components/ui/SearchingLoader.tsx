import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Globe, Search, Sparkles, CheckCircle2, ShieldCheck, Radio } from "lucide-react";

export interface SearchingLoaderProps {
  visible: boolean;
  query?: string;
}

/** A compact header status pill; displayed in the navigation / header bar */
export function SearchingLoader({ visible, query }: SearchingLoaderProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, width: 0, x: 4 }}
          animate={{ opacity: 1, width: "auto", x: 0 }}
          exit={{ opacity: 0, width: 0, x: 4 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          aria-label="Research workflow active"
          data-testid="searching-loader-pill"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            minWidth: 0,
            overflow: "hidden",
            padding: "5px 10px",
            border: "1px solid rgba(14,165,233,.35)",
            borderRadius: 999,
            color: "#0284c7",
            background: "rgba(224,242,254,.85)",
            boxShadow: "0 0 12px rgba(14, 165, 233, 0.25)",
            fontSize: 11,
            fontWeight: 750,
            letterSpacing: ".01em",
            whiteSpace: "nowrap",
          }}
        >
          <motion.span
            animate={{ rotate: 360 }}
            transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
            style={{ display: "grid", placeItems: "center" }}
          >
            <Globe size={13} style={{ color: "#0284c7" }} />
          </motion.span>
          <span>{query ? `Searching: "${query.slice(0, 24)}${query.length > 24 ? "…" : ""}"` : "Searching live web"}</span>
          <motion.span
            animate={{ opacity: [0.25, 1, 0.25] }}
            transition={{ duration: 1.15, repeat: Infinity }}
            style={{ display: "flex", gap: 2 }}
            aria-hidden="true"
          >
            {[0, 1, 2].map((dot) => (
              <i key={dot} style={{ width: 3, height: 3, borderRadius: 99, background: "currentColor" }} />
            ))}
          </motion.span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

const SEARCH_STAGES = [
  "Connecting to live 2026 search index…",
  "Retrieving real-time news & authoritative sources…",
  "Verifying facts against 2026 temporal grounding…",
  "Synthesizing live search results for HINAA…",
];

export interface WebSearchLoaderProps {
  visible: boolean;
  query?: string;
}

/** Full-fidelity inline research card rendered directly inside the chat conversation stream */
export function WebSearchLoader({ visible, query }: WebSearchLoaderProps) {
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    if (!visible) {
      setStageIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setStageIndex((prev) => (prev < SEARCH_STAGES.length - 1 ? prev + 1 : prev));
    }, 1100);
    return () => clearInterval(interval);
  }, [visible]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 10, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -8, scale: 0.98 }}
          transition={{ duration: 0.28, ease: "easeOut" }}
          data-testid="web-search-loader"
          aria-label="Searching live web"
          style={{
            position: "relative",
            overflow: "hidden",
            margin: "8px 0 16px",
            padding: "16px 20px",
            borderRadius: 16,
            background: "linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(99, 102, 241, 0.09), rgba(236, 72, 153, 0.05))",
            border: "1px solid rgba(14, 165, 233, 0.35)",
            boxShadow: "0 10px 30px -5px rgba(14, 165, 233, 0.18), 0 0 18px rgba(99, 102, 241, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.15)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            width: "100%",
            maxWidth: "min(850px, 100%)",
          }}
        >
          {/* Animated laser scanning beam */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: 2,
              overflow: "hidden",
              background: "rgba(14, 165, 233, 0.15)",
            }}
          >
            <motion.div
              animate={{ x: ["-100%", "200%"] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
              style={{
                width: "50%",
                height: "100%",
                background: "linear-gradient(90deg, transparent, #38bdf8, #818cf8, #ec4899, transparent)",
                boxShadow: "0 0 10px #38bdf8, 0 0 20px #818cf8",
              }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
            {/* Spinning Holographic Globe Icon */}
            <div style={{ position: "relative", flexShrink: 0 }}>
              {/* Outer pulsing ring */}
              <motion.div
                animate={{ scale: [1, 1.25, 1], opacity: [0.35, 0.75, 0.35] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                style={{
                  position: "absolute",
                  inset: -4,
                  borderRadius: "50%",
                  background: "radial-gradient(circle, rgba(14, 165, 233, 0.35) 0%, transparent 70%)",
                }}
              />
              <div
                style={{
                  position: "relative",
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, rgba(14, 165, 233, 0.22), rgba(99, 102, 241, 0.28))",
                  border: "1px solid rgba(14, 165, 233, 0.45)",
                  display: "grid",
                  placeItems: "center",
                  boxShadow: "0 0 14px rgba(14, 165, 233, 0.35)",
                }}
              >
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 7, repeat: Infinity, ease: "linear" }}
                  style={{ display: "grid", placeItems: "center" }}
                >
                  <Globe size={18} style={{ color: "#38bdf8" }} />
                </motion.div>
                {/* Search mini-badge */}
                <span
                  style={{
                    position: "absolute",
                    bottom: -2,
                    right: -2,
                    width: 14,
                    height: 14,
                    borderRadius: "50%",
                    background: "#0284c7",
                    border: "1.5px solid #0f172a",
                    display: "grid",
                    placeItems: "center",
                  }}
                >
                  <Search size={8} style={{ color: "#ffffff" }} />
                </span>
              </div>
            </div>

            {/* Content Area */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 750,
                      color: "var(--text-primary, #f8fafc)",
                      letterSpacing: "-0.01em",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    Searching the Live Web
                  </span>
                  {/* Live Pulsing Beacon */}
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "2px 7px",
                      borderRadius: 999,
                      background: "rgba(14, 165, 233, 0.15)",
                      border: "1px solid rgba(14, 165, 233, 0.3)",
                      color: "#38bdf8",
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "0.02em",
                      textTransform: "uppercase",
                    }}
                  >
                    <motion.span
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ duration: 1.2, repeat: Infinity }}
                      style={{
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        background: "#38bdf8",
                        boxShadow: "0 0 6px #38bdf8",
                      }}
                    />
                    2026 Grounding
                  </span>
                </div>

                {/* Animated typing dots */}
                <motion.div
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 1.2, repeat: Infinity }}
                  style={{ display: "flex", gap: 3, alignItems: "center" }}
                  aria-hidden="true"
                >
                  {[0, 1, 2].map((dot) => (
                    <motion.span
                      key={dot}
                      animate={{ y: [0, -3, 0] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: dot * 0.15 }}
                      style={{
                        width: 4,
                        height: 4,
                        borderRadius: "50%",
                        background: "#38bdf8",
                      }}
                    />
                  ))}
                </motion.div>
              </div>

              {/* Dynamic Query pill */}
              {query && (
                <div
                  style={{
                    marginTop: 6,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    padding: "3px 10px",
                    borderRadius: 6,
                    background: "rgba(15, 23, 42, 0.4)",
                    border: "1px solid rgba(14, 165, 233, 0.2)",
                    fontSize: 11,
                    color: "var(--text-secondary, #94a3b8)",
                    fontWeight: 550,
                    maxWidth: "100%",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  <Search size={11} style={{ color: "#38bdf8", flexShrink: 0 }} />
                  <span style={{ color: "#e2e8f0", fontWeight: 650 }}>Query:</span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>"{query}"</span>
                </div>
              )}

              {/* Multi-stage progressive status message */}
              <div
                style={{
                  marginTop: 8,
                  fontSize: 12,
                  color: "var(--text-secondary, #cbd5e1)",
                  fontWeight: 500,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Sparkles size={13} style={{ color: "#a855f7", flexShrink: 0 }} />
                <motion.span
                  key={stageIndex}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  {SEARCH_STAGES[stageIndex]}
                </motion.span>
              </div>

              {/* Verification Badges */}
              <div
                style={{
                  marginTop: 10,
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  flexWrap: "wrap",
                  fontSize: 10,
                  color: "var(--text-tertiary, #64748b)",
                  fontWeight: 600,
                }}
              >
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <ShieldCheck size={12} style={{ color: "#10b981" }} />
                  Cutoff Bypass Active
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <Radio size={12} style={{ color: "#38bdf8" }} />
                  Real-Time Web Feed
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <CheckCircle2 size={12} style={{ color: "#a855f7" }} />
                  Multi-Source Attributed
                </span>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
