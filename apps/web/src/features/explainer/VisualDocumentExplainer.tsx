/**
 * VisualDocumentExplainer.tsx
 *
 * Implements high-level visual explanation and interactive architecture inspect decks:
 * - Inspired by video lTJeW-Y1-BwOtJjc (ChatGPT Orion 7 Serving Floor: rotating 3D spherical
 *   lattice ribbons, 6-agent floor crew pipeline, speculation gauge, knee cost curve, stack trace).
 * - Inspired by video 7576325114997034260 & AQO9 (Korus PDF quote breakdown, VAT calculation,
 *   4 app integration tiles for Stripe, GitHub, n8n, Vercel).
 * - Inspired by video wQvDP6KmnXANaurC (generative spotlight widgets: checklist, timezone converter, split calculator).
 * - Inspired by Screamba / Document Insight (visual diagram hot-spot callouts explained in voice).
 */

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  Boxes,
  Cpu,
  Layers,
  Activity,
  CheckCircle2,
  Share2,
  Download,
  Volume2,
  Sparkles,
  Maximize2,
  Minimize2,
  X,
  Play,
  RotateCcw,
  Zap,
  Clock,
  Calculator,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import { playUiSound } from "../../lib/uiSound";

export interface VisualDocumentExplainerProps {
  isOpen: boolean;
  onClose: () => void;
  onSpeakExplanation?: (text: string) => void;
  isSpeaking?: boolean;
}

export type ExplainerDeck = "orion" | "quote" | "widgets";

export const VisualDocumentExplainer: React.FC<VisualDocumentExplainerProps> = ({
  isOpen,
  onClose,
  onSpeakExplanation,
  isSpeaking = false,
}) => {
  const [activeDeck, setActiveDeck] = useState<ExplainerDeck>("orion");
  const [isPlaying3D, setIsPlaying3D] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // ─── 3D Orion Lattice Canvas Loop ─────────────────────────────
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const rotationAngleRef = useRef(0);

  useEffect(() => {
    if (!isOpen || activeDeck !== "orion") return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let running = true;

    const renderLattice = () => {
      if (!running || !canvas) return;
      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) * 0.38;

      ctx.clearRect(0, 0, width, height);

      if (isPlaying3D) {
        rotationAngleRef.current += 0.015;
      }
      const angle = rotationAngleRef.current;

      // Draw faint background sphere grid
      ctx.strokeStyle = "rgba(0, 212, 255, 0.08)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Generate 3D ribbon strands
      const strands = [
        { color: "#00d4ff", offset: 0, width: 2.2, label: "Core Winding" },
        { color: "#ec4899", offset: Math.PI / 3, width: 2, label: "Hoop" },
        { color: "#f59e0b", offset: (2 * Math.PI) / 3, width: 2.5, label: "Shard Band" },
        { color: "#10b981", offset: Math.PI, width: 2, label: "Outflow" },
        { color: "#a855f7", offset: (4 * Math.PI) / 3, width: 1.8, label: "Poles" },
        { color: "#38bdf8", offset: (5 * Math.PI) / 3, width: 2.2, label: "Residual" },
      ];

      for (const strand of strands) {
        ctx.beginPath();
        ctx.strokeStyle = strand.color;
        ctx.lineWidth = strand.width;
        ctx.lineCap = "round";

        const points = 70;
        let started = false;

        for (let i = 0; i <= points; i++) {
          const t = (i / points) * Math.PI * 2;
          const lat = (i / points - 0.5) * Math.PI;
          const lon = t * 2 + angle + strand.offset;

          // 3D sphere coordinate
          const x3d = Math.cos(lat) * Math.cos(lon);
          const y3d = Math.sin(lat);
          const z3d = Math.cos(lat) * Math.sin(lon);

          // Perspective projection
          const pers = 1 / (1.8 - z3d * 0.4);
          const px = cx + x3d * radius * pers;
          const py = cy + y3d * radius * pers;

          // Alpha by depth
          const alpha = THREE_clamp(0.25 + (z3d + 1) * 0.35, 0.15, 0.95);
          ctx.strokeStyle = hexToRgba(strand.color, alpha);

          if (!started) {
            ctx.moveTo(px, py);
            started = true;
          } else {
            ctx.lineTo(px, py);
          }
        }
        ctx.stroke();
      }

      // Draw pole center glow
      const glowGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, radius * 0.8);
      glowGrad.addColorStop(0, "rgba(0, 212, 255, 0.12)");
      glowGrad.addColorStop(1, "transparent");
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 0.8, 0, Math.PI * 2);
      ctx.fill();

      animFrameRef.current = requestAnimationFrame(renderLattice);
    };

    renderLattice();

    return () => {
      running = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isOpen, activeDeck, isPlaying3D]);

  // ─── Generative Widgets State (from wQvDP6KmnXANaurC) ──────────
  const [checklist, setChecklist] = useState([
    { id: 1, text: "Milk", done: false },
    { id: 2, text: "Eggs", done: true },
    { id: 3, text: "Bread", done: false },
  ]);
  const [newItemText, setNewItemText] = useState("");
  const [pstHour, setPstHour] = useState(15); // 3 PM PST
  const [billAmount, setBillAmount] = useState(2400);
  const [splitPeople, setSplitPeople] = useState(3);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 99999,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(3, 7, 18, 0.82)",
          backdropFilter: "blur(16px)",
          padding: 16,
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 16 }}
          transition={{ type: "spring", stiffness: 380, damping: 28 }}
          style={{
            width: "100%",
            maxWidth: 1040,
            maxHeight: "92vh",
            background: "linear-gradient(145deg, #0b0f19 0%, #060911 100%)",
            border: "1px solid rgba(0, 212, 255, 0.25)",
            borderRadius: 20,
            boxShadow: "0 24px 60px rgba(0,0,0,0.85), inset 0 1px 0 rgba(255,255,255,0.12)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            color: "#f8fafc",
            fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif",
          }}
        >
          {/* ── Top Header Navigation Bar ────────────────────────────── */}
          <div
            style={{
              padding: "12px 18px",
              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: "rgba(15, 23, 42, 0.6)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 10,
                  background: "linear-gradient(135deg, #00d4ff 0%, #3b82f6 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 0 16px rgba(0, 212, 255, 0.4)",
                }}
              >
                <Sparkles size={16} color="#000" />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 750, letterSpacing: "-0.01em", color: "#fff" }}>
                  HINAA Visual Document & Architecture Explainer
                </div>
                <div style={{ fontSize: 11, color: "#94a3b8" }}>
                  High-level document comprehension, Orion 7 serving floor & generative widget matrix
                </div>
              </div>
            </div>

            {/* Deck Switcher Tabs */}
            <div
              style={{
                display: "flex",
                background: "rgba(255,255,255,0.06)",
                padding: 3,
                borderRadius: 10,
                border: "1px solid rgba(255,255,255,0.1)",
                gap: 4,
              }}
            >
              {[
                { id: "orion", label: "🪐 Orion 7 Serving Floor", icon: Layers },
                { id: "quote", label: "📄 PDF & Quote Engine", icon: FileText },
                { id: "widgets", label: "⚡ Generative Widgets", icon: Zap },
              ].map((tab) => {
                const Icon = tab.icon;
                const active = activeDeck === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveDeck(tab.id as ExplainerDeck);
                    }}
                    style={{
                      background: active ? "rgba(0, 212, 255, 0.2)" : "transparent",
                      border: active ? "1px solid rgba(0, 212, 255, 0.45)" : "1px solid transparent",
                      color: active ? "#00d4ff" : "#94a3b8",
                      borderRadius: 8,
                      padding: "4px 10px",
                      fontSize: 11,
                      fontWeight: 650,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      transition: "all 0.15s ease",
                    }}
                  >
                    <Icon size={12} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Action buttons */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  playUiSound("buttonPress");
                  if (activeDeck === "orion") {
                    onSpeakExplanation?.(
                      "This is the Orion 7 Serving Floor. Six agents hold the batch across a wound spherical lattice while you wait: Admitter, Sharder, Folder, Solver, Auditor, and Emitter."
                    );
                  } else if (activeDeck === "quote") {
                    onSpeakExplanation?.(
                      "This is Atelier Brun's quote PDF. The subtotal is 1,240 euros, VAT is 248 euros, bringing the final payable total to 1,488 euros with one-click Stripe and GitHub sync."
                    );
                  } else {
                    onSpeakExplanation?.(
                      "These are generative structured cards. When you type natural language, Hina parses shopping checklists, converts timezones, or splits expenses immediately."
                    );
                  }
                }}
                title="Speak explanation with HINAA"
                style={{
                  background: isSpeaking ? "rgba(16, 185, 129, 0.25)" : "rgba(0, 212, 255, 0.15)",
                  border: isSpeaking ? "1px solid #10b981" : "1px solid rgba(0, 212, 255, 0.35)",
                  color: isSpeaking ? "#10b981" : "#00d4ff",
                  borderRadius: 8,
                  padding: "4px 10px",
                  fontSize: 11,
                  fontWeight: 650,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <Volume2 size={12} />
                <span>{isSpeaking ? "Explaining…" : "Explain with Hina"}</span>
              </button>

              <button
                type="button"
                onClick={onClose}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  padding: 4,
                  borderRadius: 6,
                }}
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* ── Deck Content Area ────────────────────────────────────── */}
          <div style={{ flex: 1, overflowY: "auto", padding: 18 }}>
            {/* ══════════════════════════════════════════════════════════
                DECK 1: CHATGPT ORION 7 SERVING FLOOR (lTJeW-Y1-BwOtJjc)
               ══════════════════════════════════════════════════════════ */}
            {activeDeck === "orion" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Header Metrics Banner */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: 12,
                    padding: "8px 14px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 13, fontWeight: 800, color: "#38bdf8" }}>
                      ChatGPT Orion 7 · Serving Floor
                    </span>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>
                      SIX AGENTS HOLD THE BATCH · THE LATTICE FOLDS AROUND IT
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 16, fontFamily: "monospace", fontSize: 11 }}>
                    <div>
                      <span style={{ color: "#64748b" }}>WINDOW: </span>
                      <span style={{ color: "#fff", fontWeight: 700 }}>119K</span>
                    </div>
                    <div>
                      <span style={{ color: "#64748b" }}>SHARDS: </span>
                      <span style={{ color: "#00d4ff", fontWeight: 700 }}>8 / 72</span>
                    </div>
                    <div>
                      <span style={{ color: "#64748b" }}>OUT/S: </span>
                      <span style={{ color: "#10b981", fontWeight: 700 }}>88 tok</span>
                    </div>
                    <div>
                      <span style={{ color: "#64748b" }}>LATENCY: </span>
                      <span style={{ color: "#fbbf24", fontWeight: 700 }}>TG 153ms</span>
                    </div>
                  </div>
                </div>

                {/* 6 Floor Crew Agents Pipeline */}
                <div
                  style={{
                    background: "rgba(15, 23, 42, 0.5)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: 12,
                    padding: 10,
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 750, color: "#94a3b8", marginBottom: 8 }}>
                    THE FLOOR CREW · SIX AGENTS HOLDING THE BATCH WHILE YOU WAIT
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 6 }}>
                    {[
                      { name: "01 ADMITTER", role: "Totes the batch in", val: "42 q", active: true, color: "#38bdf8" },
                      { name: "02 SHARDER", role: "Splits it across 72", val: "42 q", active: false, color: "#818cf8" },
                      { name: "03 FOLDER", role: "Folds the lattice", val: "48 q", active: true, color: "#ec4899" },
                      { name: "04 SOLVER", role: "Runs the long pass", val: "35 q", active: false, color: "#fbbf24" },
                      { name: "05 AUDITOR", role: "Checks every claim", val: "61 q", active: false, color: "#a855f7" },
                      { name: "06 EMITTER", role: "Heads the answer back", val: "19 q", active: true, color: "#10b981" },
                    ].map((agent) => (
                      <div
                        key={agent.name}
                        style={{
                          background: agent.active ? `${agent.color}15` : "rgba(255,255,255,0.03)",
                          border: `1px solid ${agent.active ? agent.color : "rgba(255,255,255,0.06)"}`,
                          borderRadius: 8,
                          padding: "6px 8px",
                          display: "flex",
                          flexDirection: "column",
                          gap: 3,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span style={{ fontSize: 10, fontWeight: 800, color: agent.color }}>
                            {agent.name}
                          </span>
                          <span
                            style={{
                              fontSize: 8,
                              fontWeight: 700,
                              background: agent.active ? agent.color : "transparent",
                              color: agent.active ? "#000" : "#64748b",
                              padding: "1px 4px",
                              borderRadius: 4,
                            }}
                          >
                            {agent.active ? "RUN" : "WAIT"}
                          </span>
                        </div>
                        <span style={{ fontSize: 9, color: "#94a3b8" }}>{agent.role}</span>
                        <span style={{ fontSize: 10, fontFamily: "monospace", color: "#e2e8f0" }}>{agent.val}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Main 3D Spherical Lattice Ribbon Canvas + Diagnostics Grid */}
                <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 12 }}>
                  {/* Left: 3D Spherical Lattice Visualizer */}
                  <div
                    style={{
                      background: "rgba(0, 0, 0, 0.4)",
                      border: "1px solid rgba(0, 212, 255, 0.2)",
                      borderRadius: 12,
                      padding: 12,
                      position: "relative",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: 10,
                        left: 12,
                        fontSize: 11,
                        fontWeight: 750,
                        color: "#00d4ff",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <span>THE ORION LATTICE · SHAPE UNDER LOAD · LIVE</span>
                      <span
                        style={{
                          fontSize: 9,
                          background: "#ec4899",
                          color: "#fff",
                          padding: "1px 6px",
                          borderRadius: 4,
                          fontWeight: 700,
                        }}
                      >
                        SEALING
                      </span>
                    </div>

                    <canvas
                      ref={canvasRef}
                      width={440}
                      height={260}
                      style={{ width: "100%", maxHeight: 260, cursor: "grab" }}
                    />

                    {/* Canvas Controls */}
                    <div
                      style={{
                        position: "absolute",
                        bottom: 8,
                        right: 12,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setIsPlaying3D((p) => !p)}
                        style={{
                          background: "rgba(255,255,255,0.08)",
                          border: "1px solid rgba(255,255,255,0.15)",
                          color: "#fff",
                          borderRadius: 6,
                          padding: "3px 8px",
                          fontSize: 10,
                          cursor: "pointer",
                        }}
                      >
                        {isPlaying3D ? "Pause 3D" : "Rotate 3D"}
                      </button>
                    </div>

                    <div
                      style={{
                        width: "100%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        fontSize: 10,
                        fontFamily: "monospace",
                        color: "#94a3b8",
                        borderTop: "1px solid rgba(255,255,255,0.08)",
                        paddingTop: 6,
                        marginTop: 4,
                      }}
                    >
                      <span>STRANDS: 59</span>
                      <span>FORM: SHELL</span>
                      <span>FOLD: 0%</span>
                      <span>EDGE EXITS: 26</span>
                      <span>DEPTH: 1.44R</span>
                      <span>TOKENS: 631</span>
                    </div>
                  </div>

                  {/* Right: Speculation Gauge + Knee Curve + Recovery Ledger */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {/* Speculation Draft Accuracy */}
                    <div
                      style={{
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 10,
                        padding: 10,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "#fff" }}>
                          SPECULATION ACCURACY
                        </div>
                        <div style={{ fontSize: 9, color: "#94a3b8" }}>
                          WHAT THE DRAFT MODEL GOT RIGHT
                        </div>
                        <div style={{ fontSize: 10, color: "#10b981", fontWeight: 700, marginTop: 4 }}>
                          +8 GUESSED PER STEP
                        </div>
                      </div>

                      {/* Circular Gauge 74% */}
                      <div style={{ position: "relative", width: 56, height: 56 }}>
                        <svg width="56" height="56" viewBox="0 0 56 56">
                          <circle cx="28" cy="28" r="22" stroke="rgba(255,255,255,0.1)" strokeWidth="5" fill="none" />
                          <circle
                            cx="28"
                            cy="28"
                            r="22"
                            stroke="#10b981"
                            strokeWidth="5"
                            strokeDasharray={2 * Math.PI * 22}
                            strokeDashoffset={2 * Math.PI * 22 * (1 - 0.74)}
                            strokeLinecap="round"
                            fill="none"
                            transform="rotate(-90 28 28)"
                          />
                        </svg>
                        <div
                          style={{
                            position: "absolute",
                            inset: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 11,
                            fontWeight: 800,
                            color: "#10b981",
                          }}
                        >
                          74%
                        </div>
                      </div>
                    </div>

                    {/* The Knee Cost Curve */}
                    <div
                      style={{
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 10,
                        padding: 10,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 11 }}>
                        <span style={{ fontWeight: 700, color: "#fff" }}>THE KNEE · BATCH SIZE COST</span>
                        <span style={{ color: "#fb7185", fontWeight: 700, fontSize: 10 }}>AT 148 BATCH</span>
                      </div>
                      <div
                        style={{
                          height: 38,
                          marginTop: 6,
                          background: "linear-gradient(180deg, rgba(56,189,248,0.15) 0%, transparent 100%)",
                          borderRadius: 6,
                          position: "relative",
                          overflow: "hidden",
                        }}
                      >
                        <svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 100 40">
                          <path
                            d="M 0 35 Q 40 32 65 24 T 100 4"
                            fill="none"
                            stroke="#38bdf8"
                            strokeWidth="2"
                          />
                          <circle cx="65" cy="24" r="3" fill="#ec4899" />
                        </svg>
                      </div>
                    </div>

                    {/* Recovery Ledger */}
                    <div
                      style={{
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 10,
                        padding: 10,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 11 }}>
                        <span style={{ fontWeight: 700, color: "#fff" }}>RECOVERY LEDGER</span>
                        <span style={{ color: "#10b981", fontWeight: 700, fontSize: 10 }}>HELD 88.0%</span>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 6, fontSize: 10 }}>
                        <div style={{ color: "#94a3b8" }}>PREEMPTED: <span style={{ color: "#fff" }}>16</span></div>
                        <div style={{ color: "#94a3b8" }}>SPILLED: <span style={{ color: "#fff" }}>7</span></div>
                        <div style={{ color: "#94a3b8" }}>RECOMPUTED: <span style={{ color: "#fff" }}>9</span></div>
                        <div style={{ color: "#94a3b8" }}>DEADLINE MISS: <span style={{ color: "#fff" }}>13</span></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ══════════════════════════════════════════════════════════
                DECK 2: KORUS PDF & QUOTE ENGINE (7576325114997034260 & AQO9)
               ══════════════════════════════════════════════════════════ */}
            {activeDeck === "quote" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Header Row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: "rgba(239, 68, 68, 0.08)",
                    border: "1px solid rgba(239, 68, 68, 0.25)",
                    borderRadius: 12,
                    padding: "10px 14px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div
                      style={{
                        background: "#ef4444",
                        color: "#fff",
                        padding: "6px 8px",
                        borderRadius: 8,
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        fontWeight: 800,
                        fontSize: 11,
                      }}
                    >
                      <FileText size={14} />
                      <span>quote.pdf</span>
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>
                        Atelier Brun Invoice & VAT Breakdown
                      </div>
                      <div style={{ fontSize: 11, color: "#94a3b8" }}>
                        Extracted by HINAA Multimodal Vision · Valid until October 30
                      </div>
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 10, color: "#94a3b8" }}>Total Amount</div>
                    <div style={{ fontSize: 16, fontWeight: 800, color: "#10b981" }}>
                      €1,488.00 <span style={{ fontSize: 11, color: "#94a3b8" }}>incl. VAT</span>
                    </div>
                  </div>
                </div>

                {/* Line Items Table */}
                <div
                  style={{
                    background: "rgba(15, 23, 42, 0.5)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: 12,
                    padding: 12,
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#cbd5e1", marginBottom: 8 }}>
                    Line Item Breakdown
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {[
                      { desc: "Creative Brand Strategy & Identity Spec", qty: "1", unit: "€600.00", total: "€600.00" },
                      { desc: "Next.js & Supabase Architecture Core", qty: "1", unit: "€440.00", total: "€440.00" },
                      { desc: "3D Procedural WebGL Component Integration", qty: "1", unit: "€200.00", total: "€200.00" },
                    ].map((item, i) => (
                      <div
                        key={i}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "3fr 1fr 1fr 1fr",
                          background: "rgba(255,255,255,0.03)",
                          padding: "8px 12px",
                          borderRadius: 6,
                          fontSize: 11,
                        }}
                      >
                        <span style={{ color: "#f8fafc", fontWeight: 550 }}>{item.desc}</span>
                        <span style={{ color: "#94a3b8" }}>{item.qty}</span>
                        <span style={{ color: "#94a3b8" }}>{item.unit}</span>
                        <span style={{ color: "#fff", fontWeight: 700 }}>{item.total}</span>
                      </div>
                    ))}
                  </div>

                  {/* Calculations Summary */}
                  <div
                    style={{
                      marginTop: 12,
                      borderTop: "1px solid rgba(255,255,255,0.08)",
                      paddingTop: 10,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-end",
                      gap: 4,
                      fontSize: 11,
                    }}
                  >
                    <div style={{ display: "flex", gap: 24, color: "#94a3b8" }}>
                      <span>Subtotal excl. VAT:</span>
                      <span style={{ color: "#fff", fontWeight: 650 }}>€1,240.00</span>
                    </div>
                    <div style={{ display: "flex", gap: 24, color: "#94a3b8" }}>
                      <span>VAT (20.0%):</span>
                      <span style={{ color: "#fbbf24", fontWeight: 650 }}>€248.00</span>
                    </div>
                    <div style={{ display: "flex", gap: 24, fontSize: 13, fontWeight: 800, color: "#10b981", marginTop: 4 }}>
                      <span>Final Total:</span>
                      <span>€1,488.00</span>
                    </div>
                  </div>
                </div>

                {/* 4 App Integrations Dispatch Deck (from 7576325114997034260) */}
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", marginBottom: 8 }}>
                    Automated Actions & One-Click Integrations
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                    {[
                      {
                        name: "Stripe",
                        desc: "Generate €1,488 Checkout Link",
                        color: "#635bff",
                        action: () => {
                          playUiSound("success");
                          onSpeakExplanation?.("Generating Stripe payment checkout link for 1,488 euros.");
                        },
                      },
                      {
                        name: "GitHub",
                        desc: "Commit quote to /invoices repo",
                        color: "#f43f5e",
                        action: () => {
                          playUiSound("success");
                          onSpeakExplanation?.("Pushing quote.pdf archive to GitHub repository.");
                        },
                      },
                      {
                        name: "n8n",
                        desc: "Trigger Accounting Webhook",
                        color: "#f97316",
                        action: () => {
                          playUiSound("success");
                          onSpeakExplanation?.("Executing n8n automation workflow for invoice ledger.");
                        },
                      },
                      {
                        name: "Vercel",
                        desc: "Deploy Customer Portal",
                        color: "#a855f7",
                        action: () => {
                          playUiSound("success");
                          onSpeakExplanation?.("Deploying client invoice portal to Vercel Edge.");
                        },
                      },
                    ].map((integ) => (
                      <button
                        key={integ.name}
                        type="button"
                        onClick={integ.action}
                        style={{
                          background: `${integ.color}15`,
                          border: `1px solid ${integ.color}40`,
                          borderRadius: 10,
                          padding: "10px 12px",
                          textAlign: "left",
                          cursor: "pointer",
                          display: "flex",
                          flexDirection: "column",
                          gap: 4,
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ width: 8, height: 8, borderRadius: 4, background: integ.color }} />
                          <span style={{ fontSize: 12, fontWeight: 750, color: "#fff" }}>{integ.name}</span>
                        </div>
                        <span style={{ fontSize: 10, color: "#cbd5e1" }}>{integ.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ══════════════════════════════════════════════════════════
                DECK 3: GENERATIVE SPOTLIGHT WIDGETS (wQvDP6KmnXANaurC)
               ══════════════════════════════════════════════════════════ */}
            {activeDeck === "widgets" && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
                {/* Widget 1: Interactive Checklist */}
                <div
                  style={{
                    background: "rgba(15, 23, 42, 0.6)",
                    border: "1px solid rgba(0, 212, 255, 0.25)",
                    borderRadius: 14,
                    padding: 14,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <CheckCircle2 size={15} color="#00d4ff" />
                      <span style={{ fontSize: 12, fontWeight: 750, color: "#fff" }}>Shopping Checklist</span>
                    </div>
                    <span style={{ fontSize: 10, color: "#94a3b8" }}>
                      {checklist.filter((c) => c.done).length}/{checklist.length} done
                    </span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {checklist.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => {
                          playUiSound("click");
                          setChecklist((list) =>
                            list.map((c) => (c.id === item.id ? { ...c, done: !c.done } : c))
                          );
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          background: item.done ? "rgba(16, 185, 129, 0.1)" : "rgba(255,255,255,0.04)",
                          border: item.done ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid rgba(255,255,255,0.08)",
                          borderRadius: 8,
                          padding: "6px 10px",
                          cursor: "pointer",
                          fontSize: 11,
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={item.done}
                          onChange={() => {}}
                          style={{ accentColor: "#10b981" }}
                        />
                        <span
                          style={{
                            color: item.done ? "#94a3b8" : "#fff",
                            textDecoration: item.done ? "line-through" : "none",
                          }}
                        >
                          {item.text}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div style={{ display: "flex", gap: 6, marginTop: "auto" }}>
                    <input
                      type="text"
                      placeholder="Add item..."
                      value={newItemText}
                      onChange={(e) => setNewItemText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && newItemText.trim()) {
                          playUiSound("pop");
                          setChecklist((l) => [...l, { id: Date.now(), text: newItemText.trim(), done: false }]);
                          setNewItemText("");
                        }
                      }}
                      style={{
                        flex: 1,
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        borderRadius: 6,
                        padding: "4px 8px",
                        fontSize: 11,
                        color: "#fff",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (newItemText.trim()) {
                          playUiSound("pop");
                          setChecklist((l) => [...l, { id: Date.now(), text: newItemText.trim(), done: false }]);
                          setNewItemText("");
                        }
                      }}
                      style={{
                        background: "#00d4ff",
                        color: "#000",
                        fontWeight: 700,
                        border: "none",
                        borderRadius: 6,
                        padding: "4px 10px",
                        fontSize: 11,
                        cursor: "pointer",
                      }}
                    >
                      + Add
                    </button>
                  </div>
                </div>

                {/* Widget 2: Live Timezone Converter */}
                <div
                  style={{
                    background: "rgba(15, 23, 42, 0.6)",
                    border: "1px solid rgba(236, 72, 153, 0.25)",
                    borderRadius: 14,
                    padding: 14,
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Clock size={15} color="#ec4899" />
                    <span style={{ fontSize: 12, fontWeight: 750, color: "#fff" }}>Time Zone Conversion</span>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      background: "rgba(255,255,255,0.03)",
                      padding: "12px 14px",
                      borderRadius: 10,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>
                        {pstHour > 12 ? `${pstHour - 12}:00 PM` : `${pstHour}:00 AM`}
                      </div>
                      <div style={{ fontSize: 10, color: "#94a3b8" }}>Pacific Time (PT)</div>
                    </div>

                    <ArrowRight size={18} color="#ec4899" />

                    <div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: "#10b981" }}>
                        {((pstHour + 12 + 0.5) % 24) > 12
                          ? `${Math.floor(((pstHour + 12 + 0.5) % 24) - 12)}:30 PM`
                          : `${Math.floor((pstHour + 12 + 0.5) % 24)}:30 AM`}
                      </div>
                      <div style={{ fontSize: 10, color: "#94a3b8" }}>India Time (IST)</div>
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: 10, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                      Adjust PT Hour: {pstHour}:00
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={23}
                      value={pstHour}
                      onChange={(e) => setPstHour(Number(e.target.value))}
                      style={{ width: "100%", accentColor: "#ec4899" }}
                    />
                  </div>
                </div>

                {/* Widget 3: Expense / Bill Splitter */}
                <div
                  style={{
                    background: "rgba(15, 23, 42, 0.6)",
                    border: "1px solid rgba(16, 185, 129, 0.25)",
                    borderRadius: 14,
                    padding: 14,
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Calculator size={15} color="#10b981" />
                    <span style={{ fontSize: 12, fontWeight: 750, color: "#fff" }}>Instant Split Calculator</span>
                  </div>

                  <div
                    style={{
                      background: "rgba(16, 185, 129, 0.1)",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      borderRadius: 10,
                      padding: "12px 14px",
                      textAlign: "center",
                    }}
                  >
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>
                      ₹{billAmount.toLocaleString()} ÷ {splitPeople} people
                    </div>
                    <div style={{ fontSize: 22, fontWeight: 850, color: "#10b981", marginTop: 2 }}>
                      ₹{Math.round(billAmount / splitPeople).toLocaleString()}{" "}
                      <span style={{ fontSize: 12, fontWeight: 600 }}>/ each</span>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#94a3b8" }}>
                      <span>Total: ₹{billAmount}</span>
                      <span>People: {splitPeople}</span>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      {[2, 3, 4, 5].map((count) => (
                        <button
                          key={count}
                          type="button"
                          onClick={() => {
                            playUiSound("switch");
                            setSplitPeople(count);
                          }}
                          style={{
                            flex: 1,
                            background: splitPeople === count ? "#10b981" : "rgba(255,255,255,0.06)",
                            color: splitPeople === count ? "#000" : "#fff",
                            border: "none",
                            borderRadius: 6,
                            padding: "4px 0",
                            fontSize: 10,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          {count}P
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

function THREE_clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function hexToRgba(hex: string, alpha: number): string {
  let c = hex.replace("#", "");
  if (c.length === 3) c = c.split("").map((ch) => ch + ch).join("");
  const num = parseInt(c, 16);
  return `rgba(${(num >> 16) & 255}, ${(num >> 8) & 255}, ${num & 255}, ${alpha})`;
}
