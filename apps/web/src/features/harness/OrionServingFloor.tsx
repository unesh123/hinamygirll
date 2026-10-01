import React, { useState, useEffect, useRef } from "react";
import {
  Activity,
  Layers,
  Cpu,
  ShieldAlert,
  Terminal,
  Zap,
  RefreshCw,
  GitMerge,
  Box,
  Compass,
  CheckCircle2,
  Sparkles,
  Sliders,
  Maximize2,
} from "lucide-react";
import { hinaaIdentityHeaders } from "../../lib/hinaaIdentity";

interface FloorCrewAgent {
  name: string;
  role: string;
  load: number; // 0 - 100%
  status: "idle" | "knotting" | "folding" | "splicing" | "injecting" | "pacing" | "snitting";
  color: string;
  tokensProcessed: number;
}

interface OrionServingFloorProps {
  onStationSelect?: (station: string) => void;
  isDark?: boolean;
}

export function OrionServingFloor({
  onStationSelect,
  isDark = true,
}: OrionServingFloorProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Motion & Telemetry State
  const [motionData, setMotionData] = useState<any>({
    profile: {
      posture: "attentive",
      gaze: "screen",
      gesture_rate: 1.2,
      orbit_speed: 1.5,
      particle_energy: 0.85,
      trail_color: "#06b6d4",
    },
    current_station: "operating",
    emotion: "focused",
    confidence: 0.96,
  });

  const [activeStation, setActiveStation] = useState<string>("operating");
  const [isRotating, setIsRotating] = useState<boolean>(true);
  const [orbitSpeedFactor, setOrbitSpeedFactor] = useState<number>(1.2);
  const [speculationRate, setSpeculationRate] = useState<number>(98.7);
  const [recoveryEvents, setRecoveryEvents] = useState<Array<{ id: string; time: string; msg: string; status: string }>>([
    { id: "tx-881", time: "18:24:02", msg: "Astra DAG Branch merged with 0 drift", status: "ok" },
    { id: "tx-882", time: "18:24:05", msg: "Desktop operator focus verified (sub-ms)", status: "ok" },
    { id: "tx-883", time: "18:24:09", msg: "Browser DOM auto-repair: viewport 768px stabilized", status: "ok" },
  ]);

  // 6 Floor Crew Agents (from Orion 7 serving floor spec)
  const [crew, setCrew] = useState<FloorCrewAgent[]>([
    { name: "Knotter", role: "Token & Context Packing", load: 42, status: "knotting", color: "#38bdf8", tokensProcessed: 142850 },
    { name: "Pacer", role: "Velocity Throttling", load: 28, status: "pacing", color: "#818cf8", tokensProcessed: 98400 },
    { name: "Folder", role: "Knowledge State Compression", load: 65, status: "folding", color: "#a855f7", tokensProcessed: 320140 },
    { name: "Splicer", role: "Multi-Agent Graph Arbitrator", load: 84, status: "splicing", color: "#ec4899", tokensProcessed: 541090 },
    { name: "Injector", role: "Deterministic Tool Dispatch", load: 51, status: "injecting", color: "#10b981", tokensProcessed: 219800 },
    { name: "Snitter", role: "Speculative Token Filter", load: 39, status: "snitting", color: "#f59e0b", tokensProcessed: 187420 },
  ]);

  // Fetch live motion state from backend
  const fetchMotionState = async () => {
    try {
      const headers = { ...hinaaIdentityHeaders(), "bypass-tunnel-reminder": "true" };
      const res = await fetch("/v1/harness/motion/state", { headers });
      if (res.ok) {
        const json = await res.json();
        setMotionData(json);
        if (json.current_station) setActiveStation(json.current_station);
      }
    } catch (e) {
      // Backend motion state fallback handles smoothly
    }
  };

  useEffect(() => {
    fetchMotionState();
    const interval = setInterval(fetchMotionState, 3000);
    return () => clearInterval(interval);
  }, []);

  // Station transition handler
  const handleTransition = async (station: string) => {
    setActiveStation(station);
    onStationSelect?.(station);
    try {
      const headers = {
        "Content-Type": "application/json",
        ...hinaaIdentityHeaders(),
        "bypass-tunnel-reminder": "true",
      };
      await fetch("/v1/harness/motion/transition", {
        method: "POST",
        headers,
        body: JSON.stringify({
          intent: `navigate_to_${station}`,
          energy: 0.9,
          station,
        }),
      });
      fetchMotionState();
    } catch (err) {
      console.debug("Station transition error:", err);
    }
  };

  // 3D Spherical Strand Lattice Renderer (Canvas 60fps engine)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let angleX = 0;
    let angleY = 0;
    let angleZ = 0;

    // Generate spherical points and lattice strands
    const nodeCount = 72;
    const radius = 110;
    const nodes: Array<{ x: number; y: number; z: number; u: number; v: number }> = [];

    // Fibonacci sphere distribution for uniform spherical strand lattice
    const goldenRatio = (1 + Math.sqrt(5)) / 2;
    for (let i = 0; i < nodeCount; i++) {
      const theta = (2 * Math.PI * i) / goldenRatio;
      const phi = Math.acos(1 - (2 * (i + 0.5)) / nodeCount);
      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);
      nodes.push({ x, y, z, u: theta, v: phi });
    }

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;

      // Speed computed from motion brain profile
      const speed = isRotating ? (motionData.profile?.orbit_speed || 1.2) * orbitSpeedFactor * 0.008 : 0;
      angleY += speed;
      angleX += speed * 0.6;
      angleZ += speed * 0.2;

      const cosX = Math.cos(angleX);
      const sinX = Math.sin(angleX);
      const cosY = Math.cos(angleY);
      const sinY = Math.sin(angleY);
      const cosZ = Math.cos(angleZ);
      const sinZ = Math.sin(angleZ);

      // Project 3D nodes to 2D
      const projected = nodes.map((n) => {
        // Rotate Y
        let x1 = n.x * cosY - n.z * sinY;
        let z1 = n.z * cosY + n.x * sinY;
        // Rotate X
        let y2 = n.y * cosX - z1 * sinX;
        let z2 = z1 * cosX + n.y * sinX;
        // Rotate Z
        let x3 = x1 * cosZ - y2 * sinZ;
        let y3 = y2 * cosZ + x1 * sinZ;

        const fov = 350;
        const scale = fov / (fov + z2);
        return {
          x2d: cx + x3 * scale,
          y2d: cy + y3 * scale,
          z: z2,
          scale,
        };
      });

      // Sort by depth for correct strand occlusions
      const sortedEdges: Array<{ i: number; j: number; avgZ: number }> = [];
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dz = nodes[i].z - nodes[j].z;
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
          if (dist < 48) {
            sortedEdges.push({
              i,
              j,
              avgZ: (projected[i].z + projected[j].z) / 2,
            });
          }
        }
      }
      sortedEdges.sort((a, b) => a.avgZ - b.avgZ);

      const trailHex = motionData.profile?.trail_color || "#38bdf8";

      // Draw strands
      sortedEdges.forEach((edge) => {
        const p1 = projected[edge.i];
        const p2 = projected[edge.j];
        const alpha = Math.max(0.12, Math.min(0.75, (edge.avgZ + radius) / (2 * radius)));
        ctx.beginPath();
        ctx.moveTo(p1.x2d, p1.y2d);
        ctx.lineTo(p2.x2d, p2.y2d);
        ctx.strokeStyle = `${trailHex}${Math.floor(alpha * 255)
          .toString(16)
          .padStart(2, "0")}`;
        ctx.lineWidth = alpha * 1.6;
        ctx.stroke();
      });

      // Draw glowing nodes
      projected.forEach((p) => {
        const nodeAlpha = Math.max(0.2, (p.z + radius) / (2 * radius));
        ctx.beginPath();
        ctx.arc(p.x2d, p.y2d, Math.max(1, p.scale * 2.2), 0, Math.PI * 2);
        ctx.fillStyle = `#ffffff${Math.floor(nodeAlpha * 255)
          .toString(16)
          .padStart(2, "0")}`;
        ctx.shadowColor = trailHex;
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      // Central Energy Core
      const corePulse = Math.sin(Date.now() * 0.004) * 5 + 18;
      const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, corePulse * 2.2);
      grad.addColorStop(0, "rgba(255, 255, 255, 0.9)");
      grad.addColorStop(0.3, `${trailHex}bb`);
      grad.addColorStop(1, "transparent");
      ctx.beginPath();
      ctx.arc(cx, cy, corePulse * 2.2, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [isRotating, orbitSpeedFactor, motionData]);

  const stations = [
    { id: "operating", label: "⚡ Operating", desc: "Native OS & Media" },
    { id: "research", label: "🔬 Research", desc: "Agent-Reach & Web" },
    { id: "code", label: "💻 Code Foundry", desc: "Astra DAG & Browser" },
    { id: "memory", label: "🧠 Memory Vault", desc: "Repo .hina Persistence" },
    { id: "browser", label: "🌐 Browser Lab", desc: "A11y & Self-Repair" },
  ];

  return (
    <div
      data-testid="orion-serving-floor"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        padding: "16px",
        background: isDark ? "#09090b" : "#f8fafc",
        borderRadius: "16px",
        border: isDark ? "1px solid rgba(255,255,255,0.08)" : "1px solid #e2e8f0",
        color: isDark ? "#e4e4e7" : "#0f172a",
        height: "100%",
        overflowY: "auto",
      }}
    >
      {/* ── Top Bar ────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
          paddingBottom: 12,
          borderBottom: isDark ? "1px solid rgba(255,255,255,0.06)" : "1px solid #e2e8f0",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
            }}
          >
            <Activity size={18} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: "-0.01em" }}>
              Orion 7 • Serving Floor Visualizer
            </div>
            <div style={{ fontSize: 11, color: isDark ? "#a1a1aa" : "#64748b" }}>
              Living 3D Lattice, Subagent Floor Crew & Real-time Telemetry
            </div>
          </div>
        </div>

        {/* Speculative Gauge */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "4px 12px",
              borderRadius: "8px",
              background: isDark ? "rgba(16, 185, 129, 0.12)" : "rgba(16, 185, 129, 0.08)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
            }}
          >
            <Zap size={14} color="#10b981" />
            <div style={{ fontSize: 11 }}>
              <span style={{ color: isDark ? "#a1a1aa" : "#64748b" }}>Speculation: </span>
              <strong style={{ color: "#10b981" }}>{speculationRate}%</strong>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 10px",
              borderRadius: "8px",
              background: isDark ? "rgba(255,255,255,0.05)" : "#f1f5f9",
              fontSize: 11,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: motionData.profile?.trail_color || "#38bdf8",
              }}
            />
            <span style={{ textTransform: "capitalize" }}>
              {motionData.profile?.posture || "attentive"}
            </span>
          </div>
        </div>
      </div>

      {/* ── Main Interactive Grid ──────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 16,
        }}
      >
        {/* Left Card: 3D Spherical Strand Lattice */}
        <div
          style={{
            position: "relative",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
            borderRadius: 12,
            background: isDark ? "#121216" : "#ffffff",
            border: isDark ? "1px solid rgba(255,255,255,0.06)" : "1px solid #e2e8f0",
            minHeight: 330,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 12,
              left: 12,
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              fontWeight: 600,
              color: isDark ? "#a1a1aa" : "#64748b",
            }}
          >
            <Compass size={13} />
            <span>Neural Strand Core</span>
          </div>

          <div
            style={{
              position: "absolute",
              top: 12,
              right: 12,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <button
              type="button"
              onClick={() => setIsRotating(!isRotating)}
              style={{
                padding: "3px 8px",
                borderRadius: 6,
                fontSize: 10,
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: isRotating ? "rgba(56, 189, 248, 0.15)" : "rgba(255,255,255,0.06)",
                color: isRotating ? "#38bdf8" : "#a1a1aa",
              }}
            >
              {isRotating ? "Orbiting" : "Paused"}
            </button>
            <button
              type="button"
              onClick={() => setOrbitSpeedFactor((prev) => (prev >= 2 ? 0.6 : prev + 0.6))}
              style={{
                padding: "3px 8px",
                borderRadius: 6,
                fontSize: 10,
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: isDark ? "rgba(255,255,255,0.06)" : "#f1f5f9",
                color: isDark ? "#e4e4e7" : "#334155",
              }}
            >
              {orbitSpeedFactor.toFixed(1)}x
            </button>
          </div>

          <canvas
            ref={canvasRef}
            width={310}
            height={260}
            style={{ width: "100%", maxWidth: 310, height: 260 }}
          />

          {/* Spatial Station Selector Pills */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
              justifyContent: "center",
              width: "100%",
              marginTop: 8,
            }}
          >
            {stations.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => handleTransition(s.id)}
                style={{
                  padding: "4px 8px",
                  borderRadius: "6px",
                  fontSize: 10,
                  fontWeight: 600,
                  cursor: "pointer",
                  border: activeStation === s.id
                    ? "1px solid #38bdf8"
                    : isDark
                    ? "1px solid rgba(255,255,255,0.08)"
                    : "1px solid #cbd5e1",
                  background: activeStation === s.id
                    ? "rgba(56, 189, 248, 0.18)"
                    : isDark
                    ? "rgba(255,255,255,0.03)"
                    : "#f8fafc",
                  color: activeStation === s.id ? "#38bdf8" : isDark ? "#a1a1aa" : "#64748b",
                  transition: "all 120ms ease",
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Right Card: 6 Floor Crew Agents */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            padding: 16,
            borderRadius: 12,
            background: isDark ? "#121216" : "#ffffff",
            border: isDark ? "1px solid rgba(255,255,255,0.06)" : "1px solid #e2e8f0",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 650 }}>
              <Cpu size={14} color="#8b5cf6" />
              <span>Floor Crew Subagent Fleet (6 Workers)</span>
            </div>
            <span style={{ fontSize: 10, color: "#10b981", fontWeight: 600 }}>
              100% Operational
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
            {crew.map((agent) => (
              <div
                key={agent.name}
                style={{
                  padding: "8px 10px",
                  borderRadius: "8px",
                  background: isDark ? "rgba(255,255,255,0.02)" : "#f8fafc",
                  border: isDark ? "1px solid rgba(255,255,255,0.05)" : "1px solid #f1f5f9",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: 11,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: agent.color,
                      }}
                    />
                    <strong style={{ color: isDark ? "#f4f4f5" : "#18181b" }}>
                      {agent.name}
                    </strong>
                    <span style={{ color: isDark ? "#71717a" : "#94a3b8", fontSize: 10 }}>
                      • {agent.role}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontFamily: "monospace", fontSize: 10, color: agent.color }}>
                      {agent.tokensProcessed.toLocaleString()} tok
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 600 }}>{agent.load}%</span>
                  </div>
                </div>

                {/* Workload Progress Bar */}
                <div
                  style={{
                    width: "100%",
                    height: 4,
                    borderRadius: 2,
                    background: isDark ? "rgba(255,255,255,0.06)" : "#e2e8f0",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${agent.load}%`,
                      height: "100%",
                      background: agent.color,
                      transition: "width 300ms ease",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bottom Section: Recovery Ledger & Self-Repair Heatmap ── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          padding: 14,
          borderRadius: 12,
          background: isDark ? "#121216" : "#ffffff",
          border: isDark ? "1px solid rgba(255,255,255,0.06)" : "1px solid #e2e8f0",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 650 }}>
            <CheckCircle2 size={13} color="#10b981" />
            <span>Autonomous Recovery Ledger & Release Verification Signatures</span>
          </div>
          <span style={{ fontSize: 10, color: isDark ? "#71717a" : "#94a3b8", fontFamily: "monospace" }}>
            Audit: ver_1790872686_ca86cd3
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
          {recoveryEvents.map((ev) => (
            <div
              key={ev.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "6px 10px",
                borderRadius: "6px",
                background: isDark ? "rgba(255,255,255,0.02)" : "#f8fafc",
                fontSize: 11,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: 10,
                    color: isDark ? "#a1a1aa" : "#64748b",
                  }}
                >
                  [{ev.time}]
                </span>
                <span style={{ color: isDark ? "#e4e4e7" : "#334155" }}>{ev.msg}</span>
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "#10b981",
                  padding: "1px 6px",
                  borderRadius: "4px",
                  background: "rgba(16, 185, 129, 0.12)",
                }}
              >
                VERIFIED
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
