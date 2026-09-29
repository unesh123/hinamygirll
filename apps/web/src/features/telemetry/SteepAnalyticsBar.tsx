import React, { useState, useEffect, useCallback } from "react";
import {
  Activity,
  Cpu,
  Clock,
  Zap,
  Terminal,
  ShieldCheck,
  RefreshCw,
  Bell,
  CheckCircle2,
  Sliders,
} from "lucide-react";

interface SteepAnalyticsBarProps {
  activeModel?: string;
  contextTokens?: number;
  maxContextTokens?: number;
  lastLatencyMs?: number | null;
  onOpenTerminal?: () => void;
  onOpenVault?: () => void;
  onOpenPulseDrawer?: () => void;
}

export function SteepAnalyticsBar({
  activeModel = "qwen3.8-max",
  contextTokens = 42850,
  maxContextTokens = 1000000, // 1M context window
  lastLatencyMs = 850,
  onOpenTerminal,
  onOpenVault,
  onOpenPulseDrawer,
}: SteepAnalyticsBarProps) {
  const [heartbeatState, setHeartbeatState] = useState<{
    isRunning: boolean;
    pulsesEmitted: number;
    lastTickTime: string | null;
    intervalSeconds: number;
  }>({
    isRunning: true,
    pulsesEmitted: 0,
    lastTickTime: null,
    intervalSeconds: 180,
  });

  const [isTicking, setIsTicking] = useState(false);
  const [tickFeedback, setTickFeedback] = useState<string | null>(null);

  // Poll heartbeat status
  const fetchHeartbeat = useCallback(async () => {
    try {
      const res = await fetch("/v1/heartbeat/status");
      if (res.ok) {
        const data = await res.json();
        setHeartbeatState({
          isRunning: Boolean(data.isRunning),
          pulsesEmitted: data.pulsesEmittedCount || 0,
          lastTickTime: data.lastTickTime,
          intervalSeconds: data.intervalSeconds || 180,
        });
      }
    } catch {
      // Background poll failure is non-blocking
    }
  }, []);

  useEffect(() => {
    fetchHeartbeat();
    const interval = setInterval(fetchHeartbeat, 15000);
    return () => clearInterval(interval);
  }, [fetchHeartbeat]);

  const handleForceTick = async () => {
    if (isTicking) return;
    setIsTicking(true);
    try {
      const res = await fetch("/v1/heartbeat/tick", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        fetchHeartbeat();
        setTickFeedback("Pulse Emitted!");
        setTimeout(() => setTickFeedback(null), 2500);
      }
    } catch (err) {
      console.error("Manual pulse tick failed", err);
    } finally {
      setIsTicking(false);
    }
  };

  const contextPercent = Math.min(100, Math.round((contextTokens / maxContextTokens) * 100));

  return (
    <div
      className="steep-analytics-bar"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        backgroundColor: "#ffffff",
        borderBottom: "1px solid #e8e3dc",
        padding: "6px 20px",
        fontSize: 12,
        color: "#57534e",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        flexShrink: 0,
        zIndex: 20,
      }}
    >
      {/* ── Left: Steep Editorial Brand & Model Readout ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              fontFamily: "'Newsreader', 'Signifier', 'Georgia', serif",
              fontWeight: 600,
              fontSize: 13,
              color: "#1c1917",
              letterSpacing: "-0.01em",
            }}
          >
            STEEP
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              backgroundColor: "#fbe1d1", // Peach accent
              color: "#833d1c",
              padding: "1px 6px",
              borderRadius: 4,
            }}
          >
            Editorial Engine
          </span>
        </div>

        <div style={{ width: 1, height: 14, backgroundColor: "#e8e3dc" }} />

        {/* Model ID */}
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <Cpu size={13} style={{ color: "#78716c" }} />
          <span style={{ color: "#1c1917", fontWeight: 600 }}>{activeModel}</span>
        </div>

        {/* Latency */}
        {lastLatencyMs != null && (
          <div style={{ display: "flex", alignItems: "center", gap: 4, color: "#78716c" }}>
            <Clock size={12} />
            <span>{lastLatencyMs}ms</span>
          </div>
        )}
      </div>

      {/* ── Middle: 1M Context Window Meter ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, color: "#78716c", fontWeight: 500 }}>Context Window:</span>
          <div
            style={{
              width: 110,
              height: 6,
              backgroundColor: "#f5f3ef",
              borderRadius: 9999,
              overflow: "hidden",
              border: "1px solid #e8e3dc",
            }}
          >
            <div
              style={{
                width: `${Math.max(4, contextPercent)}%`,
                height: "100%",
                backgroundColor: contextPercent > 80 ? "#f97316" : "#1c1917",
                borderRadius: 9999,
                transition: "width 0.4s ease",
              }}
            />
          </div>
          <span style={{ fontSize: 11, color: "#1c1917", fontWeight: 600 }}>
            {contextTokens.toLocaleString()} / {(maxContextTokens / 1000000).toFixed(1)}M
          </span>
        </div>

        <div style={{ width: 1, height: 14, backgroundColor: "#e8e3dc" }} />

        {/* Heartbeat Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: heartbeatState.isRunning ? "#10b981" : "#94a3b8",
              boxShadow: heartbeatState.isRunning ? "0 0 6px rgba(16, 185, 129, 0.4)" : "none",
            }}
          />
          <span style={{ fontSize: 11, color: "#78716c" }}>
            Pulse: <strong style={{ color: "#1c1917" }}>{heartbeatState.pulsesEmitted}</strong> emitted
          </span>
          <button
            type="button"
            onClick={handleForceTick}
            disabled={isTicking}
            title="Trigger immediate heartbeat pulse"
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
            <RefreshCw size={11} style={{ animation: isTicking ? "spin 1s linear infinite" : "none" }} />
          </button>
          {tickFeedback && (
            <span style={{ fontSize: 10, color: "#16a34a", fontWeight: 600 }}>
              {tickFeedback}
            </span>
          )}
        </div>
      </div>

      {/* ── Right: Executive Quick Links ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {onOpenVault && (
          <button
            type="button"
            onClick={onOpenVault}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              backgroundColor: "#f5f3ef",
              color: "#1c1917",
              border: "1px solid #e8e3dc",
              borderRadius: 6,
              padding: "3px 8px",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <ShieldCheck size={12} />
            VIP Vault
          </button>
        )}

        {onOpenTerminal && (
          <button
            type="button"
            onClick={onOpenTerminal}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              backgroundColor: "#1c1917",
              color: "#ffffff",
              border: "none",
              borderRadius: 6,
              padding: "3px 8px",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Terminal size={12} />
            Terminal
          </button>
        )}
      </div>
    </div>
  );
}
