export interface Particle {
  active: boolean;
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  life: number;
  maxLife: number;
  color: string;
  gravity: number;
  shape: "circle" | "square" | "spark";
}

export class ParticleSystem {
  private pool: Particle[];
  private cursor = 0;

  constructor(capacity = 520) {
    this.pool = Array.from({ length: capacity }, () => ({
      active: false,
      x: 0,
      y: 0,
      vx: 0,
      vy: 0,
      size: 3,
      life: 0,
      maxLife: 1,
      color: "#22d3ee",
      gravity: 400,
      shape: "circle" as const,
    }));
  }

  clear(): void {
    for (const p of this.pool) p.active = false;
  }

  emit(opts: {
    x: number;
    y: number;
    vx: number;
    vy: number;
    size?: number;
    life?: number;
    color: string;
    gravity?: number;
    shape?: Particle["shape"];
  }): void {
    const p = this.pool[this.cursor]!;
    this.cursor = (this.cursor + 1) % this.pool.length;
    p.active = true;
    p.x = opts.x;
    p.y = opts.y;
    p.vx = opts.vx;
    p.vy = opts.vy;
    p.size = opts.size ?? 3.5;
    p.maxLife = opts.life ?? 0.55;
    p.life = p.maxLife;
    p.color = opts.color;
    p.gravity = opts.gravity ?? 420;
    p.shape = opts.shape ?? "circle";
  }

  emitBurst(
    x: number,
    y: number,
    count: number,
    color: string,
    speed = 220,
    shape: Particle["shape"] = "spark",
  ): void {
    for (let i = 0; i < count; i++) {
      const ang = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.4;
      const spd = speed * (0.35 + Math.random() * 0.85);
      this.emit({
        x,
        y,
        vx: Math.cos(ang) * spd,
        vy: Math.sin(ang) * spd - 60,
        size: 2.5 + Math.random() * 3.5,
        life: 0.35 + Math.random() * 0.45,
        color,
        gravity: 560,
        shape,
      });
    }
  }

  emitDust(x: number, y: number, color = "#d6b48a", count = 3): void {
    for (let i = 0; i < count; i++) {
      this.emit({
        x: x + (Math.random() - 0.5) * 12,
        y: y - Math.random() * 4,
        vx: -40 - Math.random() * 75,
        vy: -20 - Math.random() * 65,
        size: 3 + Math.random() * 4.5,
        life: 0.35 + Math.random() * 0.35,
        color,
        gravity: 110,
        shape: "circle",
      });
    }
  }

  emitBoostFlame(x: number, y: number, vx: number, vy: number): void {
    this.emit({
      x,
      y,
      vx: vx * 0.25 - 120 - Math.random() * 90,
      vy: vy * 0.25 + (Math.random() - 0.5) * 65,
      size: 4.5 + Math.random() * 3.5,
      life: 0.24 + Math.random() * 0.14,
      color: Math.random() > 0.45 ? "#22d3ee" : "#f472b6",
      gravity: -30,
      shape: "circle",
    });
  }

  emitDebris(x: number, y: number, kind: "crate" | "barrier" | "cone"): void {
    const palette =
      kind === "crate"
        ? ["#c2783f", "#8c5126", "#eab308"]
        : kind === "barrier"
          ? ["#ef4444", "#f8fafc", "#38bdf8"]
          : ["#f97316", "#f8fafc"];
    for (let i = 0; i < 14; i++) {
      const col = palette[i % palette.length]!;
      this.emit({
        x: x + (Math.random() - 0.5) * 18,
        y: y + (Math.random() - 0.5) * 18,
        vx: 80 + Math.random() * 240,
        vy: -110 - Math.random() * 230,
        size: 4 + Math.random() * 5,
        life: 0.55 + Math.random() * 0.45,
        color: col,
        gravity: 820,
        shape: "square",
      });
    }
  }

  update(dt: number): void {
    for (const p of this.pool) {
      if (!p.active) continue;
      p.life -= dt;
      if (p.life <= 0) {
        p.active = false;
        continue;
      }
      p.vy += p.gravity * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    for (const p of this.pool) {
      if (!p.active) continue;
      const alpha = Math.max(0, Math.min(1, p.life / p.maxLife));
      ctx.globalAlpha = alpha;
      ctx.fillStyle = p.color;
      if (p.shape === "square") {
        ctx.fillRect(p.x - p.size * 0.5, p.y - p.size * 0.5, p.size, p.size);
      } else if (p.shape === "spark") {
        ctx.strokeStyle = p.color;
        ctx.lineWidth = Math.max(1.5, p.size * 0.45);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x - p.vx * 0.025, p.y - p.vy * 0.025);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
  }
}
