import { useRef, useEffect, useMemo } from "react";
import { motion } from "framer-motion";

export type OrbState =
  | "idle"
  | "listening"
  | "understanding"
  | "planning"
  | "delegating"
  | "working"
  | "speaking"
  | "awaiting_approval"
  | "success"
  | "error"
  | "offline";

interface HinaaOrbProps {
  state: OrbState;
  audioLevel?: number;
  size?: number;
  className?: string;
}

const STATE_COLORS: Record<OrbState, { from: string; to: string; glow: string }> = {
  idle: { from: "#F36F9C", to: "#FFB598", glow: "rgba(243, 111, 156, 0.20)" },
  listening: { from: "#9CCFEA", to: "#9EDFC8", glow: "rgba(156, 207, 234, 0.30)" },
  understanding: { from: "#B8A7F2", to: "#9CCFEA", glow: "rgba(184, 167, 242, 0.25)" },
  planning: { from: "#B8A7F2", to: "#F36F9C", glow: "rgba(184, 167, 242, 0.25)" },
  delegating: { from: "#FFB598", to: "#B8A7F2", glow: "rgba(255, 181, 152, 0.25)" },
  working: { from: "#9EDFC8", to: "#9CCFEA", glow: "rgba(158, 223, 200, 0.25)" },
  speaking: { from: "#F36F9C", to: "#B8A7F2", glow: "rgba(243, 111, 156, 0.30)" },
  awaiting_approval: { from: "#E9A23B", to: "#FFB598", glow: "rgba(233, 162, 59, 0.25)" },
  success: { from: "#4FB989", to: "#9EDFC8", glow: "rgba(79, 185, 137, 0.30)" },
  error: { from: "#DE5F70", to: "#FFB598", glow: "rgba(222, 95, 112, 0.25)" },
  offline: { from: "#988B94", to: "#6E626B", glow: "rgba(152, 139, 148, 0.15)" },
};

const STATE_ANIMATIONS: Record<OrbState, { scale: number[]; duration: number }> = {
  idle: { scale: [1, 1.02, 1], duration: 4 },
  listening: { scale: [1, 1.08, 1], duration: 1.5 },
  understanding: { scale: [1, 1.04, 0.98, 1], duration: 2.5 },
  planning: { scale: [1, 1.03, 1], duration: 3 },
  delegating: { scale: [1, 1.06, 1], duration: 2 },
  working: { scale: [1, 1.04, 1], duration: 2 },
  speaking: { scale: [0.97, 1.06, 0.97], duration: 0.6 },
  awaiting_approval: { scale: [1, 1.02, 1], duration: 2 },
  success: { scale: [0.9, 1.1, 1], duration: 0.6 },
  error: { scale: [1, 0.94, 1], duration: 0.8 },
  offline: { scale: [1, 1, 1], duration: 4 },
};

export function HinaaOrb({
  state,
  audioLevel = 0,
  size = 160,
  className = "",
}: HinaaOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);

  const colors = STATE_COLORS[state];
  const anim = STATE_ANIMATIONS[state];
  const level = Math.max(0, Math.min(1, audioLevel));

  // Canvas-based orb rendering for smooth audio-reactive visuals
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = size;
    const h = size;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    let running = true;
    const animate = () => {
      if (!running) return;
      timeRef.current += 0.016;
      const t = timeRef.current;

      ctx.clearRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2;
      const baseRadius = size * 0.32;

      // Outer glow
      const glowRadius = baseRadius * (1.4 + level * 0.3);
      const glowGrad = ctx.createRadialGradient(cx, cy, baseRadius * 0.5, cx, cy, glowRadius);
      glowGrad.addColorStop(0, colors.glow);
      glowGrad.addColorStop(1, "transparent");
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2);
      ctx.fill();

      // Main orb body with breathing
      const breathe = Math.sin(t * (2 / anim.duration)) * 0.02;
      const audioReact = state === "listening" ? level * 0.08 : 0;
      const r = baseRadius * (1 + breathe + audioReact);

      // Gradient body
      const bodyGrad = ctx.createRadialGradient(
        cx - r * 0.2, cy - r * 0.3, r * 0.1,
        cx, cy, r
      );
      bodyGrad.addColorStop(0, "rgba(255, 255, 255, 0.95)");
      bodyGrad.addColorStop(0.3, colors.from + "CC");
      bodyGrad.addColorStop(0.7, colors.from + "99");
      bodyGrad.addColorStop(1, colors.to + "66");

      ctx.fillStyle = bodyGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Inner highlight
      const highlightGrad = ctx.createRadialGradient(
        cx - r * 0.25, cy - r * 0.25, 0,
        cx - r * 0.15, cy - r * 0.15, r * 0.5
      );
      highlightGrad.addColorStop(0, "rgba(255, 255, 255, 0.6)");
      highlightGrad.addColorStop(1, "transparent");
      ctx.fillStyle = highlightGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Listening waveform ring
      if (state === "listening" && level > 0.05) {
        ctx.strokeStyle = colors.from + "80";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < 360; i++) {
          const angle = (i * Math.PI) / 180;
          const waveR = r + Math.sin(angle * 8 + t * 4) * level * 12;
          const x = cx + Math.cos(angle) * waveR;
          const y = cy + Math.sin(angle) * waveR;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }

      // Speaking waveform radiating outward
      if (state === "speaking") {
        for (let ring = 0; ring < 3; ring++) {
          const ringR = r + 8 + ring * 10 + Math.sin(t * 3 + ring) * 4;
          const alpha = 0.15 - ring * 0.04;
          ctx.strokeStyle = colors.from + Math.round(alpha * 255).toString(16).padStart(2, "0");
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // Planning segmented ring
      if (state === "planning") {
        for (let i = 0; i < 8; i++) {
          const angle = (i * Math.PI * 2) / 8 + t * 0.5;
          const segR = r + 12;
          const x = cx + Math.cos(angle) * segR;
          const y = cy + Math.sin(angle) * segR;
          ctx.fillStyle = colors.from + "60";
          ctx.beginPath();
          ctx.arc(x, y, 3, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animate();
    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
    };
  }, [state, level, size, colors, anim.duration]);

  return (
    <motion.div
      className={`sakura-orb ${className}`}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      style={{
        width: size,
        height: size,
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
        }}
      />

      {/* State label */}
      <motion.div
        key={state}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        style={{
          position: "absolute",
          bottom: -8,
          left: "50%",
          transform: "translateX(-50%)",
          fontFamily: "var(--font-retro)",
          fontSize: "var(--text-xs)",
          color: colors.from,
          fontWeight: 500,
          whiteSpace: "nowrap",
          letterSpacing: "var(--tracking-wide)",
          textTransform: "uppercase",
          opacity: 0.8,
        }}
      >
        {state.replace(/_/g, " ")}
      </motion.div>
    </motion.div>
  );
}
