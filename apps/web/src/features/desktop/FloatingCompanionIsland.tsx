/**
 * HINAA Floating Companion Island & Living Computational Object HUD.
 *
 * Implements the continuous motion computational core inspired by HINAA's Motion Brain:
 * - Central morphing, rotating 3D geometric core with flowing plasma trajectory rings
 * - Real-time acoustic viseme reactive aura
 * - Compact draggable HUD with quick vocal & textual actuation
 * - Ability to control the entire UI and desktop directly
 */

import React, { useState, useEffect } from "react";
import { Mic, MicOff, Send, Terminal, Maximize2, Sparkles, Activity } from "lucide-react";
import { hinaaUIController } from "../ui-control/HinaaUIController";

interface FloatingCompanionIslandProps {
  companionName?: string;
  companionState?: string;
  isVoiceActive?: boolean;
  onToggleVoice?: () => void;
  onSendText?: (text: string) => void;
  streamingText?: string;
  onExpandWorkspace?: () => void;
}

export function FloatingCompanionIsland({
  companionName = "Hinaa",
  companionState = "idle",
  isVoiceActive = false,
  onToggleVoice,
  onSendText,
  streamingText = "",
  onExpandWorkspace,
}: FloatingCompanionIslandProps) {
  const [inputText, setInputText] = useState("");
  const [rotationAngle, setRotationAngle] = useState(0);

  // Smooth 60fps rotational trajectory loop for the living computational core
  useEffect(() => {
    let animId: number;
    const animate = () => {
      setRotationAngle((prev) => (prev + 0.8) % 360);
      animId = requestAnimationFrame(animate);
    };
    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, []);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    if (onSendText) {
      onSendText(inputText.trim());
    }
    setInputText("");
  };

  const getStatusColor = () => {
    switch (companionState) {
      case "speaking":
        return "#10b981"; // Emerald
      case "thinking":
        return "#8b5cf6"; // Violet
      case "operating":
        return "#06b6d4"; // Cyan
      case "error":
        return "#ef4444"; // Red
      default:
        return "#a855f7"; // Neon Purple
    }
  };

  const statusColor = getStatusColor();

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        width: "100%",
        height: "100%",
        padding: "16px",
        background: "radial-gradient(circle at center, rgba(30, 16, 50, 0.85) 0%, rgba(10, 10, 12, 0.98) 100%)",
        color: "#fff",
        boxSizing: "border-box",
        position: "relative",
        userSelect: "none",
      }}
    >
      {/* ── Top Bar: Telemetry & Actions ───────────────────────── */}
      <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: statusColor,
              boxShadow: `0 0 10px ${statusColor}`,
            }}
          />
          <span style={{ fontWeight: 700, fontSize: "12px", letterSpacing: "0.5px" }}>{companionName}</span>
          <span
            style={{
              fontSize: "9px",
              padding: "1px 6px",
              borderRadius: "10px",
              background: "rgba(255, 255, 255, 0.08)",
              color: statusColor,
              textTransform: "uppercase",
              fontFamily: "monospace",
              fontWeight: 600,
            }}
          >
            {companionState}
          </span>
        </div>

        <div style={{ display: "flex", gap: "6px" }}>
          <button
            onClick={() => hinaaUIController.dispatch({ action: "toggle_drawer", drawer: "terminal", open: true })}
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "#a1a1aa",
              borderRadius: "6px",
              padding: "4px",
              cursor: "pointer",
            }}
            title="Open Terminal Hands"
          >
            <Terminal size={13} />
          </button>
          <button
            onClick={onExpandWorkspace}
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "#a1a1aa",
              borderRadius: "6px",
              padding: "4px",
              cursor: "pointer",
            }}
            title="Expand to Full Workspace"
          >
            <Maximize2 size={13} />
          </button>
        </div>
      </div>

      {/* ── Center: Living Computational Object (3D Morphing Core) ─ */}
      <div
        style={{
          position: "relative",
          width: "180px",
          height: "180px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "12px 0",
        }}
      >
        {/* Outer Plasma Orbit Ring */}
        <div
          style={{
            position: "absolute",
            width: "170px",
            height: "170px",
            borderRadius: "50%",
            border: `2px dashed ${statusColor}`,
            opacity: 0.35,
            transform: `rotate(${rotationAngle}deg)`,
            transition: "border-color 0.3s ease",
          }}
        />

        {/* Counter-Rotating Gyroscope Ring */}
        <div
          style={{
            position: "absolute",
            width: "140px",
            height: "140px",
            borderRadius: "50%",
            border: `1.5px solid rgba(56, 189, 248, 0.4)`,
            transform: `rotate(${-rotationAngle * 1.5}deg) scale(0.95)`,
          }}
        />

        {/* Dense Glowing Core */}
        <div
          style={{
            width: "90px",
            height: "90px",
            borderRadius: "50%",
            background: `radial-gradient(circle, ${statusColor} 0%, rgba(139, 92, 246, 0.3) 70%, transparent 100%)`,
            boxShadow: `0 0 35px ${statusColor}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            animation: "pulse 2.5s infinite ease-in-out",
          }}
        >
          <Sparkles size={28} color="#fff" />
        </div>
      </div>

      {/* ── Subtitle / Thoughts Stream ─────────────────────────── */}
      <div
        style={{
          width: "100%",
          minHeight: "36px",
          maxHeight: "60px",
          overflowY: "auto",
          textAlign: "center",
          fontSize: "11px",
          color: "#cbd5e1",
          lineHeight: "1.35",
          padding: "4px 8px",
          background: "rgba(0, 0, 0, 0.3)",
          borderRadius: "6px",
          border: "1px solid rgba(255, 255, 255, 0.05)",
          marginBottom: "10px",
        }}
      >
        {streamingText || "Autonomous companion ready. Speak or enter a command below."}
      </div>

      {/* ── Bottom Controls: Voice & Input Bar ──────────────────── */}
      <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "8px" }}>
        <form onSubmit={handleSend} style={{ display: "flex", gap: "6px", width: "100%" }}>
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Tell Hina what to do..."
            style={{
              flex: 1,
              background: "#141418",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              padding: "7px 10px",
              color: "#fff",
              fontSize: "11px",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={!inputText.trim()}
            style={{
              background: statusColor,
              border: "none",
              borderRadius: "8px",
              padding: "0 10px",
              color: "#fff",
              cursor: "pointer",
              opacity: inputText.trim() ? 1 : 0.4,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Send size={13} />
          </button>
        </form>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button
            onClick={onToggleVoice}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 12px",
              borderRadius: "20px",
              border: "none",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: 600,
              background: isVoiceActive ? "#ef4444" : "rgba(255, 255, 255, 0.1)",
              color: "#fff",
            }}
          >
            {isVoiceActive ? <MicOff size={13} /> : <Mic size={13} />}
            {isVoiceActive ? "Mute Voice" : "Live Voice"}
          </button>

          <button
            onClick={() => hinaaUIController.dispatch({ action: "switch_mode", mode: "showroom" })}
            style={{
              background: "transparent",
              border: "none",
              color: "#a855f7",
              fontSize: "11px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              fontWeight: 600,
            }}
          >
            <Activity size={12} /> 3D Showroom
          </button>
        </div>
      </div>
    </div>
  );
}
