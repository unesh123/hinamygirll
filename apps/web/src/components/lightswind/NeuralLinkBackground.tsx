// NeuralLinkBackground — adapted from lightswind.com (open-source)
// Full canvas-based neural network animation with router/pulse/gravity interaction modes

import { useEffect, useRef } from "react";
import { useInView } from "framer-motion";

export type NeuralInteraction = "router" | "pulse" | "gravity" | "none";

interface NeuralLinkProps {
  nodeColor?: string;
  lineColor?: string;
  packetColor?: string;
  nodeCount?: number;
  maxDistance?: number;
  interactionMode?: NeuralInteraction;
  interactive?: boolean;
  packetFrequency?: number;
  className?: string;
}

interface Node {
  x: number; y: number; vx: number; vy: number;
  radius: number; baseSpeed: number; pulseScale: number;
}

interface Packet {
  id: number; x: number; y: number; path: number[];
  pathIndex: number; progress: number; speed: number;
  size: number; color: string;
}

const NeuralLinkBackground = ({
  nodeColor = "#a855f7",
  packetColor = "#00f0ff",
  nodeCount = 80,
  maxDistance = 120,
  interactionMode = "router",
  interactive = true,
  packetFrequency = 2500,
  className = "",
}: NeuralLinkProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(containerRef);
  const mouseRef = useRef({ x: 0, y: 0, active: false, radius: 180, lastX: 0, lastY: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf: number;
    let nodes: Node[] = [];
    let packets: Packet[] = [];
    let lastTime = performance.now();
    let packetId = 0;
    let autoTimer = 0;

    const mkNode = (w: number, h: number): Node => {
      const a = Math.random() * Math.PI * 2;
      const s = 0.2 + Math.random() * 0.4;
      return { x: Math.random() * w, y: Math.random() * h, vx: Math.cos(a) * s, vy: Math.sin(a) * s, radius: 1.5 + Math.random() * 2.5, baseSpeed: s, pulseScale: 1 };
    };

    const resize = () => {
      const r = containerRef.current?.getBoundingClientRect();
      const w = r?.width || window.innerWidth;
      const h = r?.height || window.innerHeight;
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w; canvas.height = h;
        nodes = Array.from({ length: nodeCount }, () => mkNode(w, h));
        packets = [];
      }
    };
    resize();

    const neighbors = (idx: number) => {
      const n1 = nodes[idx]; if (!n1) return [];
      return nodes.map((n2, i) => {
        if (i === idx) return -1;
        const d = Math.hypot(n2.x - n1.x, n2.y - n1.y);
        return d < maxDistance ? i : -1;
      }).filter(i => i >= 0);
    };

    const spawnPacket = (startIdx: number, fromCursor = false) => {
      const path: number[] = [startIdx];
      let cur = startIdx;
      for (let hop = 0; hop < 5; hop++) {
        const nb = neighbors(cur).filter(n => !path.includes(n));
        if (!nb.length) break;
        const next = nb[Math.floor(Math.random() * nb.length)];
        path.push(next); cur = next;
      }
      if (path.length < 2) return;
      const m = mouseRef.current;
      packets.push({
        id: packetId++,
        x: fromCursor ? m.x : nodes[startIdx].x,
        y: fromCursor ? m.y : nodes[startIdx].y,
        path, pathIndex: 0, progress: 0,
        speed: 0.035 + Math.random() * 0.025,
        size: 2.5 + Math.random() * 2,
        color: packetColor,
      });
      nodes[startIdx].pulseScale = 2.5;
    };

    const onMove = (e: MouseEvent) => {
      const r = canvas.getBoundingClientRect();
      const m = mouseRef.current;
      m.x = e.clientX - r.left; m.y = e.clientY - r.top; m.active = true;
      if (interactionMode === "router") {
        const dx = m.x - m.lastX, dy = m.y - m.lastY;
        if (Math.hypot(dx, dy) > 35) {
          let minD = Infinity, closest = 0;
          nodes.forEach((n, i) => { const d = Math.hypot(n.x - m.x, n.y - m.y); if (d < minD) { minD = d; closest = i; } });
          if (minD < m.radius) { spawnPacket(closest, true); m.lastX = m.x; m.lastY = m.y; }
        }
      }
    };
    const onLeave = () => { mouseRef.current.active = false; };
    const onClick = () => {
      if (!interactive) return;
      const m = mouseRef.current;
      nodes.map((n, i) => ({ i, d: Math.hypot(n.x - m.x, n.y - m.y) }))
        .sort((a, b) => a.d - b.d).slice(0, 4)
        .forEach(({ i, d }) => { if (d < m.radius * 1.5) spawnPacket(i, true); });
    };

    if (interactive) {
      canvas.addEventListener("mousemove", onMove);
      canvas.addEventListener("mouseleave", onLeave);
      canvas.addEventListener("click", onClick);
    }

    const render = (t: number) => {
      raf = requestAnimationFrame(render);
      if (!isInView) return;
      const dt = t - lastTime; lastTime = t;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      if (packetFrequency > 0) {
        autoTimer += dt;
        if (autoTimer >= packetFrequency) {
          autoTimer = 0;
          spawnPacket(Math.floor(Math.random() * nodes.length), false);
        }
      }

      const m = mouseRef.current;
      for (const n of nodes) {
        if (interactive && m.active && interactionMode === "gravity") {
          const dx = m.x - n.x, dy = m.y - n.y;
          const d = Math.hypot(dx, dy);
          if (d < m.radius) { const p = (1 - d / m.radius) * 0.15; n.vx += dx / d * p; n.vy += dy / d * p; }
        }
        n.x += n.vx; n.y += n.vy;
        const sp = Math.hypot(n.vx, n.vy);
        if (sp > n.baseSpeed) { n.vx *= 0.95; n.vy *= 0.95; }
        if (n.x < 0) n.x = w; else if (n.x > w) n.x = 0;
        if (n.y < 0) n.y = h; else if (n.y > h) n.y = 0;
        n.pulseScale = Math.max(1, n.pulseScale - 0.04);
      }

      // Draw connections
      ctx.lineWidth = 0.5;
      for (let i = 0; i < nodes.length; i++) {
        const n1 = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const n2 = nodes[j];
          const d = Math.hypot(n2.x - n1.x, n2.y - n1.y);
          if (d < maxDistance) {
            const a = (1 - d / maxDistance) * 0.12;
            ctx.strokeStyle = `rgba(168,85,247,${a})`;
            ctx.beginPath(); ctx.moveTo(n1.x, n1.y); ctx.lineTo(n2.x, n2.y); ctx.stroke();
          }
        }
        if (interactive && m.active) {
          const d = Math.hypot(m.x - n1.x, m.y - n1.y);
          if (d < m.radius) {
            const a = (1 - d / m.radius) * 0.3;
            ctx.strokeStyle = `rgba(0,240,255,${a})`;
            ctx.lineWidth = 0.8;
            ctx.beginPath(); ctx.moveTo(m.x, m.y); ctx.lineTo(n1.x, n1.y); ctx.stroke();
          }
        }
      }

      // Draw nodes
      for (const n of nodes) {
        ctx.fillStyle = nodeColor;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.radius * n.pulseScale, 0, Math.PI * 2); ctx.fill();
        if (n.pulseScale > 1.1) {
          ctx.strokeStyle = nodeColor; ctx.lineWidth = 1;
          ctx.globalAlpha = (n.pulseScale - 1) / 1.5;
          ctx.beginPath(); ctx.arc(n.x, n.y, n.radius * n.pulseScale * 1.8, 0, Math.PI * 2); ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }

      // Draw packets
      for (let i = packets.length - 1; i >= 0; i--) {
        const p = packets[i];
        p.progress += p.speed;
        if (p.progress >= 1) {
          p.progress = 0; p.pathIndex++;
          if (p.pathIndex >= p.path.length - 1) { packets.splice(i, 1); continue; }
          const ni = nodes[p.path[p.pathIndex]];
          if (ni) ni.pulseScale = 2;
        }
        const na = nodes[p.path[p.pathIndex]];
        const nb = nodes[p.path[p.pathIndex + 1]];
        if (!na || !nb) { packets.splice(i, 1); continue; }
        p.x = na.x + (nb.x - na.x) * p.progress;
        p.y = na.y + (nb.y - na.y) * p.progress;
        ctx.shadowBlur = 10; ctx.shadowColor = p.color;
        ctx.fillStyle = p.color;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
      }
    };

    raf = requestAnimationFrame(render);
    const ro = new ResizeObserver(resize);
    if (containerRef.current) ro.observe(containerRef.current);

    return () => {
      cancelAnimationFrame(raf); ro.disconnect();
      if (interactive) {
        canvas.removeEventListener("mousemove", onMove);
        canvas.removeEventListener("mouseleave", onLeave);
        canvas.removeEventListener("click", onClick);
      }
    };
  }, [nodeColor, packetColor, nodeCount, maxDistance, interactionMode, interactive, packetFrequency, isInView]);

  return (
    <div ref={containerRef} className={`absolute inset-0 w-full h-full overflow-hidden pointer-events-none ${className}`} style={{ zIndex: 0 }}>
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" style={{ display: "block", pointerEvents: "auto" }} />
    </div>
  );
};

export default NeuralLinkBackground;
