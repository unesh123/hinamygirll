import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Footprints,
  Sliders,
  Terminal,
  Zap,
  Cpu,
  Layers,
  Sparkles,
  Camera,
  Play,
  Pause,
  RotateCcw,
} from "lucide-react";
import { playUiSound } from "../../lib/uiSound";

export interface AdobeMotionTimelineProps {
  isDark?: boolean;
  activeModel?: string;
  latencyMs?: number;
  tokensUsed?: number;
  totalTokens?: number;
  isWalking?: boolean;
  onToggleWalk?: () => void;
  onOpenTerminal?: () => void;
  isVoiceActive?: boolean;
  companionState?: string;
  messageCount?: number;
  showCompanionButton?: boolean;
  onShowCompanion?: () => void;
}

export const AdobeMotionTimeline: React.FC<AdobeMotionTimelineProps> = React.memo(({
  isDark = true,
  activeModel,
  latencyMs,
  tokensUsed,
  totalTokens,
  isWalking = false,
  onToggleWalk,
  onOpenTerminal,
  isVoiceActive = false,
  companionState = "ready",
  messageCount,
  showCompanionButton,
  onShowCompanion,
}) => {
  const [activeKeyframe, setActiveKeyframe] = useState<number>(3);
  const [fps, setFps] = useState<number>(60);

  const contextPercent = tokensUsed !== undefined && totalTokens !== undefined && totalTokens > 0 ? Math.min(100, Math.round((tokensUsed / totalTokens) * 100)) : null;

  return (
    <div
      data-testid="adobe-motion-timeline"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 14px",
        background: isDark
          ? "linear-gradient(90deg, #090a0f 0%, #10131d 50%, #090a0f 100%)"
          : "linear-gradient(90deg, #f8fafc 0%, #edf2f7 50%, #f8fafc 100%)",
        borderBottom: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid #e2e8f0",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'JetBrains Mono', 'SF Pro Text', monospace",
        userSelect: "none",
        flexShrink: 0,
        gap: 12,
        overflowX: "auto",
      }}
    >
      {/* ── Left: Adobe Track Label & 3D Locomotion Indicator ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            background: isDark ? "rgba(0, 212, 255, 0.12)" : "rgba(0, 160, 220, 0.1)",
            border: isDark ? "1px solid rgba(0, 212, 255, 0.3)" : "1px solid rgba(0, 160, 220, 0.25)",
            padding: "2px 7px",
            borderRadius: 6,
          }}
        >
          <Sliders size={11} color="#00d4ff" />
          <span style={{ fontSize: 10, fontWeight: 750, color: "#00d4ff", letterSpacing: "0.04em" }}>
            3D MOTION RUNTIME
          </span>
        </div>

        {/* Walk / Roam Indicator & Toggle */}
        <button
          type="button"
          onClick={() => {
            playUiSound("buttonPress");
            onToggleWalk?.();
          }}
          title="Toggle 3D Procedural Walk & Runway Roaming"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            background: isWalking
              ? "rgba(236, 72, 153, 0.2)"
              : isDark
              ? "rgba(255, 255, 255, 0.06)"
              : "#ffffff",
            border: isWalking
              ? "1px solid #ec4899"
              : isDark
              ? "1px solid rgba(255, 255, 255, 0.12)"
              : "1px solid #cbd5e1",
            color: isWalking ? "#ec4899" : isDark ? "#ffffff" : "#0f172a",
            padding: "3px 8px",
            borderRadius: 6,
            fontSize: 10,
            fontWeight: 700,
            cursor: "pointer",
            transition: "all 0.12s ease",
          }}
        >
          <Footprints size={12} />
          <span>{isWalking ? "WALK ACTIVE" : "GAIT IDLE"}</span>
        </button>

        {/* Message count */}
        {messageCount !== undefined && messageCount > 0 && (
          <span style={{ fontSize: 10, color: isDark ? "#94a3b8" : "#64748b", fontWeight: 600 }}>
            · {messageCount} {messageCount === 1 ? "message" : "messages"}
          </span>
        )}
      </div>

      {/* ── Center: Adobe Keyframe Sequence Track ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          flex: 1,
          justifyContent: "center",
          minWidth: 260,
        }}
      >
        <span style={{ fontSize: 10, color: isDark ? "#64748b" : "#94a3b8", fontWeight: 600 }}>TRACK:</span>

        {[
          { id: 1, label: "01 INTENT", color: "#f43f5e" },
          { id: 2, label: "02 REASON", color: "#f59e0b" },
          { id: 3, label: "03 TOOL", color: "#00d4ff" },
          { id: 4, label: "04 AVATAR", color: "#10b981" },
          { id: 5, label: "05 RENDER", color: "#a855f7" },
        ].map((kf) => (
          <button
            key={kf.id}
            type="button"
            onClick={() => {
              playUiSound("click");
              setActiveKeyframe(kf.id);
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 6px",
              borderRadius: 4,
              border: activeKeyframe === kf.id ? `1px solid ${kf.color}` : "1px solid transparent",
              background: activeKeyframe === kf.id ? `${kf.color}22` : "transparent",
              color: activeKeyframe === kf.id ? kf.color : isDark ? "#94a3b8" : "#64748b",
              fontSize: 9,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <span
              style={{
                width: 5,
                height: 5,
                borderRadius: 2.5,
                background: kf.color,
                boxShadow: activeKeyframe === kf.id ? `0 0 6px ${kf.color}` : "none",
              }}
            />
            <span>{kf.label}</span>
          </button>
        ))}
      </div>

      {/* ── Right: Telemetry Gauges (FPS, Latency, Context, Visualizer) ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        {/* Latency Meter */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: isDark ? "#cbd5e1" : "#475569" }}>
          <Zap size={11} color="#f59e0b" />
          <span style={{ fontWeight: 700, color: isDark ? "#ffffff" : "#0f172a" }}>{latencyMs !== undefined ? `${Math.round(latencyMs)} ms` : "Awaiting turn"}</span>
        </div>

        {/* Context Window Gauge */}
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ fontSize: 9, color: isDark ? "#94a3b8" : "#64748b" }}>CTX:</span>
          <div
            style={{
              width: 50,
              height: 5,
              borderRadius: 3,
              background: isDark ? "rgba(255,255,255,0.1)" : "#e2e8f0",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${contextPercent ?? 0}%`,
                height: "100%",
                background: "#00d4ff",
                boxShadow: "0 0 6px #00d4ff",
              }}
            />
          </div>
          <span style={{ fontSize: 9, fontWeight: 700, color: isDark ? "#ffffff" : "#0f172a" }}>{contextPercent !== null ? `${contextPercent}%` : "Unreported"}</span>
        </div>

        {/* Audio Visualizer Spectrum Bars */}
        <div
          title={isVoiceActive ? "Voice streaming active" : "Voice engine standby"}
          style={{ display: "flex", alignItems: "center", gap: 2, height: 12 }}
        >
          {[0.6, 1.0, 0.4, 0.9, 0.5].map((h, i) => (
            <motion.div
              key={i}
              animate={{
                height: isVoiceActive ? [3, Math.round(12 * h), 3] : 3,
              }}
              transition={{
                repeat: Infinity,
                duration: 0.4 + i * 0.1,
                ease: "easeInOut",
              }}
              style={{
                width: 2,
                borderRadius: 1,
                background: isVoiceActive ? "#10b981" : isDark ? "rgba(255,255,255,0.2)" : "#cbd5e1",
              }}
            />
          ))}
        </div>

        {/* Show Companion Panel Toggle */}
        {showCompanionButton && onShowCompanion && (
          <button
            type="button"
            onClick={onShowCompanion}
            aria-label="Show companion panel"
            title="Show companion panel"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 7px",
              borderRadius: 5,
              border: isDark ? "1px solid rgba(255, 255, 255, 0.14)" : "1px solid #cbd5e1",
              background: isDark ? "rgba(255, 255, 255, 0.08)" : "#f8fafc",
              color: isDark ? "#ffffff" : "#0f172a",
              fontSize: 10,
              fontWeight: 650,
              cursor: "pointer",
            }}
          >
            <span>Companion</span>
          </button>
        )}

        {/* Terminal Button */}
        {onOpenTerminal && (
          <button
            type="button"
            onClick={() => {
              playUiSound("click");
              onOpenTerminal();
            }}
            title="Open CLI Terminal"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: isDark ? "rgba(255, 255, 255, 0.08)" : "#f1f5f9",
              border: isDark ? "1px solid rgba(255, 255, 255, 0.14)" : "1px solid #cbd5e1",
              color: isDark ? "#ffffff" : "#0f172a",
              padding: "2px 7px",
              borderRadius: 5,
              fontSize: 10,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <Terminal size={10} />
            <span>CLI</span>
          </button>
        )}
      </div>
    </div>
  );
});

