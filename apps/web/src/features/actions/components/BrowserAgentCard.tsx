import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Globe, Play, Square, Pause, ExternalLink, MousePointer, ShieldCheck, Check } from "lucide-react";
import type { BrowserAgentFields } from "../types";

interface BrowserAgentCardProps {
  data: BrowserAgentFields;
  onCommit?: (updated: BrowserAgentFields) => void;
  compact?: boolean;
}

export function BrowserAgentCard({ data, onCommit, compact = false }: BrowserAgentCardProps) {
  const [isLive, setIsLive] = useState(data.isLive);
  const [currentAction, setCurrentAction] = useState(data.lastAction);
  const [stepIndex, setStepIndex] = useState(0);

  const steps = [
    "Navigating to cloud browser session…",
    "Locating target element and calculating click coordinates…",
    "Sending synthesized mouse click event…",
    "Streaming live viewport frames back to HINA…",
  ];

  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(() => {
      setStepIndex((prev) => {
        const next = (prev + 1) % steps.length;
        setCurrentAction(steps[next]);
        return next;
      });
    }, 2200);
    return () => clearInterval(interval);
  }, [isLive, steps]);

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
              background: "rgba(99, 102, 241, 0.15)",
              color: "#6366f1",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Globe size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>HINA Cloud Browser Agent</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: isLive ? "#10b981" : "#64748b",
              boxShadow: isLive ? "0 0 8px #10b981" : "none",
            }}
          />
          <span style={{ fontSize: "0.72rem", color: isLive ? "#10b981" : "rgba(255,255,255,0.5)", fontWeight: 600 }}>
            {isLive ? "LIVE SESSION" : "PAUSED"}
          </span>
        </div>
      </div>

      {/* Cloud Browser Viewport Simulator */}
      <div
        style={{
          borderRadius: 10,
          background: "#0d131a",
          border: "1px solid rgba(255,255,255,0.08)",
          overflow: "hidden",
        }}
      >
        {/* Fake Browser Chrome Top Bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 12px",
            background: "rgba(255,255,255,0.04)",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            fontSize: "0.72rem",
            color: "rgba(255,255,255,0.6)",
          }}
        >
          <div style={{ display: "flex", gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444" }} />
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} />
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981" }} />
          </div>
          <div
            style={{
              flex: 1,
              padding: "2px 8px",
              borderRadius: 4,
              background: "rgba(0,0,0,0.4)",
              fontFamily: "monospace",
              color: "#a5b4fc",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {data.currentUrl}
          </div>
          <ExternalLink size={12} color="rgba(255,255,255,0.4)" />
        </div>

        {/* Browser Screen / Canvas view */}
        <div
          style={{
            height: 110,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "16px",
            position: "relative",
            background: "radial-gradient(ellipse at center, rgba(99, 102, 241, 0.08) 0%, transparent 70%)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#6366f1" }}>
            <MousePointer size={18} />
            <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#ffffff" }}>
              {data.pageTitle}
            </span>
          </div>

          <div
            style={{
              fontSize: "0.75rem",
              color: "rgba(255,255,255,0.7)",
              marginTop: 8,
              textAlign: "center",
            }}
          >
            ⚡ {currentAction}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <button
          type="button"
          onClick={() => setIsLive(!isLive)}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 12px",
            borderRadius: 8,
            background: isLive ? "rgba(239, 68, 68, 0.15)" : "#6366f1",
            color: isLive ? "#ef4444" : "#ffffff",
            border: isLive ? "1px solid rgba(239, 68, 68, 0.3)" : "none",
            fontSize: "0.78rem",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          {isLive ? <Pause size={13} /> : <Play size={13} fill="#fff" />}
          <span>{isLive ? "Pause Browser" : "Resume Browser"}</span>
        </button>

        <button
          type="button"
          onClick={() => {
            window.open(data.currentUrl, "_blank");
          }}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.06)",
            color: "#ffffff",
            border: "1px solid rgba(255,255,255,0.1)",
            fontSize: "0.78rem",
            fontWeight: 650,
            cursor: "pointer",
          }}
        >
          <ExternalLink size={13} />
          <span>Take Over Tab</span>
        </button>
      </div>

      {/* Safety badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.7rem", color: "rgba(255,255,255,0.4)" }}>
        <ShieldCheck size={13} color="#10b981" />
        <span>Safe cloud sandbox: payments, passwords, and form submissions require manual confirm</span>
      </div>

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() => onCommit({ ...data, isLive, lastAction: currentAction })}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            background: "#6366f1",
            color: "#ffffff",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 2,
          }}
        >
          <Check size={14} />
          <span>Keep Browser Task in Stack ↵</span>
        </button>
      )}
    </div>
  );
}
