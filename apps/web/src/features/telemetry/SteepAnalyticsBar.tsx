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
import { Stat } from "../../components/StatusBar";
import { useStatus } from "../../hooks/useStatus";

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
  const status = useStatus();
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
        minWidth: 0,
      }}
    >
      {/* ── Left: Steep Editorial Brand & Model Readout ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
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

        <div style={{ width: 1, height: 14, backgroundColor: "#e8e3dc", flexShrink: 0 }} />

        {/* Model ID */}
        <div style={{ display: "flex", alignItems: "center", gap: 5, minWidth: 0 }}>
          <Cpu size={13} style={{ color: "#78716c", flexShrink: 0 }} />
          <span style={{ color: "#1c1917", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {activeModel}
          </span>
        </div>
      </div>

      {/* ── Middle: Live Telemetry Metrics (flex gap-6 tabular-nums, NO COLLISION) ── */}
      <div
        className="telemetry-cluster"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 24, // gap-6
          fontVariantNumeric: "tabular-nums",
          flexShrink: 0,
        }}
      >
        <Stat label="TRACK" value={`${status.trackMs} ms`} />
        <Stat label="CTX" value={`${status.ctxPct}%`} />
        <Stat label="RENDER" value={`${status.renderFps} fps`} />
        <Stat label="MSGS" value={status.msgCount} highlight />
      </div>

      {/* ── Right: Executive Quick Links ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
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
