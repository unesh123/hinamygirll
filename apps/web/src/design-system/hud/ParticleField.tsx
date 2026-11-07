import { useEffect, useRef } from "react";

/** Sparse drifting particles on a canvas. Renders one static frame under reduced motion. */
export function ParticleField({ count = 48 }: { count?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext?.("2d");
    if (!canvas || !ctx) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
    const color = getComputedStyle(document.documentElement).getPropertyValue("--ds-accent").trim() || "currentColor";
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    const resize = () => {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const dots = Array.from({ length: count }, () => ({
      x: Math.random(), y: Math.random(), r: 0.6 + Math.random() * 1.6, v: 0.0006 + Math.random() * 0.0018,
    }));
    let raf = 0;
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = color;
      for (const d of dots) {
        if (!reduced) d.y = d.y - d.v < 0 ? 1 : d.y - d.v;
        ctx.globalAlpha = 0.25 + d.r * 0.2;
        ctx.beginPath();
        ctx.arc(d.x * w, d.y * h, d.r, 0, Math.PI * 2);
        ctx.fill();
      }
      if (!reduced) raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [count]);
  return <canvas ref={ref} className="ds-particles" aria-hidden="true" />;
}
