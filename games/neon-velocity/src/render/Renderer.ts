import type {
  BikeLiveryId,
  BikeState,
  GameSettings,
  GhostSample,
} from "../types/game.ts";
import type { GeneratedWorld } from "../terrain/LevelGenerator.ts";
import { SURFACE_TABLE } from "../terrain/TerrainSystem.ts";
import { getWheelWorldPositions, WHEEL_RADIUS } from "../physics/BikePhysics.ts";
import type { CameraSystem } from "../camera/CameraSystem.ts";
import type { ParticleSystem } from "../effects/ParticleSystem.ts";
import { LIVERIES } from "../save/SaveManager.ts";
import type { DebugFlags } from "../debug/DebugOverlay.ts";

interface SkyPalette {
  top: string;
  mid: string;
  bottom: string;
  farCity: string;
  midCity: string;
  windowLit: string;
  ambientGlow: string;
}

const SKY_PALETTES: Record<GameSettings["timeOfDay"], SkyPalette> = {
  night: {
    top: "#050711",
    mid: "#0d1329",
    bottom: "#1b1438",
    farCity: "#0b1024",
    midCity: "#131b38",
    windowLit: "#38bdf8",
    ambientGlow: "rgba(236, 72, 153, 0.16)",
  },
  evening: {
    top: "#170c2e",
    mid: "#4a1c4f",
    bottom: "#b44b44",
    farCity: "#1d1035",
    midCity: "#2b1745",
    windowLit: "#fbbf24",
    ambientGlow: "rgba(251, 146, 60, 0.2)",
  },
  day: {
    top: "#0c3559",
    mid: "#1d5d8c",
    bottom: "#6fb3d2",
    farCity: "#1a3b5c",
    midCity: "#244d73",
    windowLit: "#e0f2fe",
    ambientGlow: "rgba(56, 189, 248, 0.18)",
  },
};

export class GameRenderer {
  private viewWidth = 1280;
  private viewHeight = 800;
  private dpr = 1;

  resize(canvas: HTMLCanvasElement, lowQuality: boolean): void {
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(320, Math.round(rect.width || window.innerWidth));
    const h = Math.max(320, Math.round(rect.height || window.innerHeight));
    const maxDpr = lowQuality ? 1.25 : 2;
    this.dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
    this.viewWidth = w;
    this.viewHeight = h;
    const targetW = Math.round(w * this.dpr);
    const targetH = Math.round(h * this.dpr);
    if (canvas.width !== targetW || canvas.height !== targetH) {
      canvas.width = targetW;
      canvas.height = targetH;
    }
  }

  getSize(): { width: number; height: number } {
    return { width: this.viewWidth, height: this.viewHeight };
  }

  render(opts: {
    ctx: CanvasRenderingContext2D;
    world: GeneratedWorld;
    bike: BikeState;
    camera: CameraSystem;
    particles: ParticleSystem;
    settings: GameSettings;
    elapsedSec: number;
    ghostSample: GhostSample | null;
    debugFlags: DebugFlags;
  }): void {
    const { ctx, world, bike, camera, particles, settings, elapsedSec, ghostSample, debugFlags } = opts;
    const w = this.viewWidth;
    const h = this.viewHeight;

    ctx.save();
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

    // 1. Sky backdrop & Urban Parallax Layers
    this.drawSkyAndParallax(ctx, w, h, camera, settings, elapsedSec);

    // 2. World Transform
    const { offsetX, offsetY, zoom } = camera.getRenderOffset(w, h);
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(zoom, zoom);

    const viewLeft = camera.x - w / (2 * zoom) - 240;
    const viewRight = camera.x + w / (2 * zoom) + 240;

    this.drawTerrain(ctx, world, viewLeft, viewRight, settings.lowQuality);
    this.drawMovingPlatforms(ctx, world);
    this.drawHazards(ctx, world, elapsedSec);
    this.drawProps(ctx, world);
    this.drawCheckpointsAndFinish(ctx, world, elapsedSec);
    this.drawCollectibles(ctx, world, elapsedSec);

    if (ghostSample && settings.ghostEnabled) {
      this.drawGhostBike(ctx, ghostSample, liveryColors(settings.livery));
    }

    this.drawBikeAndRider(ctx, bike, settings, elapsedSec);
    particles.render(ctx);

    if (debugFlags.showSplines) {
      this.drawDebugSplines(ctx, world, viewLeft, viewRight);
    }
    if (debugFlags.showHitboxes) {
      this.drawDebugHitboxes(ctx, bike);
    }

    ctx.restore();

    // 3. Weather + Speed Lines + Minimap overlays
    this.drawWeatherOverlay(ctx, w, h, bike, settings, elapsedSec);
    this.drawMinimap(ctx, w, world, bike);

    ctx.restore();
  }

  private drawSkyAndParallax(
    ctx: CanvasRenderingContext2D,
    w: number,
    h: number,
    camera: CameraSystem,
    settings: GameSettings,
    elapsedSec: number,
  ): void {
    const pal = SKY_PALETTES[settings.timeOfDay];
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, pal.top);
    grad.addColorStop(0.58, pal.mid);
    grad.addColorStop(1, pal.bottom);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // Celestial orb (Moon or Sunset/Day Sun)
    const sunX = w * 0.78 - (camera.x * 0.01) % (w * 0.3);
    const sunY = settings.timeOfDay === "day" ? h * 0.18 : h * 0.24;
    const sunColor = settings.timeOfDay === "night" ? "#e0e7ff" : settings.timeOfDay === "evening" ? "#fb7185" : "#fef08a";
    ctx.fillStyle = sunColor;
    ctx.beginPath();
    ctx.arc(sunX, sunY, settings.timeOfDay === "night" ? 26 : 38, 0, Math.PI * 2);
    ctx.fill();

    // Horizon glow haze
    ctx.fillStyle = pal.ambientGlow;
    ctx.fillRect(0, h * 0.48, w, h * 0.52);

    // Far Skyline (parallax 0.12)
    this.drawSkylineBand(ctx, w, h, camera.x * 0.12, h * 0.62, pal.farCity, pal.windowLit, 130, 175, !settings.lowQuality, elapsedSec, 11);

    // Monorail transit track & glowing shuttle in midground (0.2x)
    const railY = h * 0.67;
    ctx.fillStyle = "rgba(15, 23, 42, 0.72)";
    ctx.fillRect(0, railY, w, 6);
    const trainWorldX = (elapsedSec * 165 - camera.x * 0.2) % (w + 460);
    const trainX = trainWorldX < -220 ? trainWorldX + w + 460 : trainWorldX;
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(trainX, railY - 12, 148, 12);
    ctx.fillStyle = "#22d3ee";
    for (let i = 0; i < 6; i++) {
      ctx.fillRect(trainX + 12 + i * 22, railY - 9, 14, 5);
    }

    // Mid Skyline (parallax 0.28)
    this.drawSkylineBand(ctx, w, h, camera.x * 0.28, h * 0.78, pal.midCity, pal.windowLit, 92, 135, !settings.lowQuality, elapsedSec, 23);
  }

  private drawSkylineBand(
    ctx: CanvasRenderingContext2D,
    w: number,
    h: number,
    scroll: number,
    baseY: number,
    fillColor: string,
    winColor: string,
    minHeight: number,
    stepW: number,
    drawWindows: boolean,
    elapsedSec: number,
    seedBias: number,
  ): void {
    const startIdx = Math.floor(scroll / stepW) - 1;
    const count = Math.ceil(w / stepW) + 3;
    ctx.fillStyle = fillColor;
    for (let i = 0; i < count; i++) {
      const idx = startIdx + i;
      const sx = idx * stepW - scroll;
      const hash = Math.abs(Math.sin(idx * 12.9898 + seedBias) * 43758.5453) % 1;
      const bh = minHeight + hash * 170;
      const bw = stepW * (0.72 + (hash * 0.22));
      const by = baseY - bh;
      ctx.fillStyle = fillColor;
      ctx.fillRect(sx, by, bw, h - by);

      if (hash > 0.76) {
        // Neon roof billboard accent
        ctx.fillStyle = idx % 2 === 0 ? "#ec4899" : "#22d3ee";
        ctx.fillRect(sx + 8, by - 4, bw * 0.45, 3);
      }

      if (drawWindows) {
        ctx.fillStyle = winColor;
        ctx.globalAlpha = 0.28;
        const cols = Math.max(2, Math.floor(bw / 18));
        const rows = Math.max(2, Math.floor(bh / 26));
        for (let r = 1; r < Math.min(7, rows); r++) {
          for (let c = 0; c < cols; c++) {
            const winHash = ((idx * 7 + r * 13 + c * 5) % 11);
            if (winHash < 4) continue;
            if ((winHash === 5) && Math.sin(elapsedSec * 1.4 + idx + r) < -0.5) continue;
            ctx.fillRect(sx + 7 + c * 15, by + 10 + r * 20, 7, 10);
          }
        }
        ctx.globalAlpha = 1;
      }
    }
  }

  private drawTerrain(
    ctx: CanvasRenderingContext2D,
    world: GeneratedWorld,
    viewLeft: number,
    viewRight: number,
    lowQuality: boolean,
  ): void {
    const pts = world.points;
    if (pts.length < 2) return;

    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i]!;
      const b = pts[i + 1]!;
      if (b.x < viewLeft || a.x > viewRight) continue;
      if (a.gap || b.gap) continue;

      const stats = SURFACE_TABLE[a.surface];
      // Underground solid earth / urban deck slab
      ctx.fillStyle = stats.color;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.lineTo(b.x, b.y + 420);
      ctx.lineTo(a.x, a.y + 420);
      ctx.closePath();
      ctx.fill();

      // Surface deck neon trim
      ctx.strokeStyle = stats.accent;
      ctx.lineWidth = a.surface === "beam" ? 5 : 4;
      if (!lowQuality) {
        ctx.shadowColor = stats.accent;
        ctx.shadowBlur = 8;
      }
      ctx.beginPath();
      ctx.moveTo(a.x, a.y + 1);
      ctx.lineTo(b.x, b.y + 1);
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Overhead Tunnel Arch
      if (a.tunnelRoofY != null && b.tunnelRoofY != null) {
        ctx.fillStyle = "#080b18";
        ctx.beginPath();
        ctx.moveTo(a.x, a.tunnelRoofY - 120);
        ctx.lineTo(b.x, b.tunnelRoofY - 120);
        ctx.lineTo(b.x, b.tunnelRoofY);
        ctx.lineTo(a.x, a.tunnelRoofY);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = "#818cf8";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(a.x, a.tunnelRoofY);
        ctx.lineTo(b.x, b.tunnelRoofY);
        ctx.stroke();

        // Warm sodium/neon tunnel strips every ~110px
        if (i % 2 === 0) {
          ctx.fillStyle = "#c084fc";
          ctx.fillRect((a.x + b.x) * 0.5 - 16, (a.tunnelRoofY + b.tunnelRoofY) * 0.5 + 2, 32, 4);
        }
      }

      // Bridge vertical suspension cables
      if (a.surface === "bridge" && i % 2 === 0) {
        ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(a.x, a.y - 88);
        ctx.stroke();
      }
    }
  }

  private drawMovingPlatforms(ctx: CanvasRenderingContext2D, world: GeneratedWorld): void {
    for (const p of world.platforms) {
      const stats = SURFACE_TABLE[p.surface];
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(p.x, p.y, p.width, p.height);
      ctx.strokeStyle = stats.accent;
      ctx.lineWidth = 3;
      ctx.strokeRect(p.x, p.y, p.width, p.height);

      // Thruster underside glow
      ctx.fillStyle = "rgba(34, 211, 238, 0.38)";
      ctx.fillRect(p.x + 18, p.y + p.height, 26, 7);
      ctx.fillRect(p.x + p.width - 44, p.y + p.height, 26, 7);
    }
  }

  private drawProps(ctx: CanvasRenderingContext2D, world: GeneratedWorld): void {
    for (const pr of world.props) {
      if (pr.broken) continue;
      if (pr.kind === "crate") {
        ctx.fillStyle = "#92400e";
        ctx.fillRect(pr.x, pr.y, pr.width, pr.height);
        ctx.strokeStyle = "#f59e0b";
        ctx.lineWidth = 2;
        ctx.strokeRect(pr.x, pr.y, pr.width, pr.height);
        ctx.beginPath();
        ctx.moveTo(pr.x, pr.y);
        ctx.lineTo(pr.x + pr.width, pr.y + pr.height);
        ctx.moveTo(pr.x + pr.width, pr.y);
        ctx.lineTo(pr.x, pr.y + pr.height);
        ctx.stroke();
      } else if (pr.kind === "barrier") {
        ctx.fillStyle = "#1e293b";
        ctx.fillRect(pr.x, pr.y, pr.width, pr.height);
        ctx.fillStyle = "#f43f5e";
        ctx.fillRect(pr.x + 2, pr.y + 6, pr.width - 4, 8);
        ctx.fillStyle = "#f8fafc";
        ctx.fillRect(pr.x + 2, pr.y + 20, pr.width - 4, 8);
      } else {
        ctx.fillStyle = "#f97316";
        ctx.beginPath();
        ctx.moveTo(pr.x + pr.width * 0.5, pr.y);
        ctx.lineTo(pr.x + pr.width, pr.y + pr.height);
        ctx.lineTo(pr.x, pr.y + pr.height);
        ctx.closePath();
        ctx.fill();
      }
    }
  }

  private drawHazards(ctx: CanvasRenderingContext2D, world: GeneratedWorld, elapsedSec: number): void {
    for (const h of world.hazards) {
      if (h.kind === "spikes") {
        ctx.fillStyle = "#ef4444";
        const teeth = Math.max(4, Math.floor(h.width / 12));
        const step = h.width / teeth;
        for (let i = 0; i < teeth; i++) {
          ctx.beginPath();
          ctx.moveTo(h.x + i * step, h.y + h.height);
          ctx.lineTo(h.x + (i + 0.5) * step, h.y);
          ctx.lineTo(h.x + (i + 1) * step, h.y + h.height);
          ctx.closePath();
          ctx.fill();
        }
      } else {
        const pulse = 0.5 + 0.5 * Math.sin(elapsedSec * 14);
        ctx.fillStyle = "#0f172a";
        ctx.fillRect(h.x, h.y + 4, h.width, h.height - 4);
        ctx.strokeStyle = pulse > 0.5 ? "#38bdf8" : "#f472b6";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(h.x, h.y + 6);
        const segs = 6;
        for (let i = 1; i <= segs; i++) {
          const sx = h.x + (h.width * i) / segs;
          const sy = h.y + (i % 2 === 0 ? 11 : 1) + Math.sin(elapsedSec * 25 + i) * 3;
          ctx.lineTo(sx, sy);
        }
        ctx.stroke();
      }
    }
  }

  private drawCollectibles(ctx: CanvasRenderingContext2D, world: GeneratedWorld, elapsedSec: number): void {
    for (const c of world.collectibles) {
      if (c.collected) continue;
      const bob = Math.sin(elapsedSec * 3.5 + c.bobPhase) * 5;
      const cy = c.y + bob;
      ctx.save();
      ctx.translate(c.x, cy);
      if (c.kind === "star") {
        ctx.fillStyle = "#facc15";
        ctx.strokeStyle = "#fef08a";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < 10; i++) {
          const r = i % 2 === 0 ? 13 : 6;
          const a = (Math.PI * i) / 5 - Math.PI / 2;
          if (i === 0) ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r);
          else ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.fillStyle = "#22d3ee";
        ctx.strokeStyle = "#ecfeff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, -11);
        ctx.lineTo(9, 0);
        ctx.lineTo(0, 11);
        ctx.lineTo(-9, 0);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  private drawCheckpointsAndFinish(ctx: CanvasRenderingContext2D, world: GeneratedWorld, elapsedSec: number): void {
    for (const cp of world.checkpoints) {
      const col = cp.triggered ? "#34d399" : "#38bdf8";
      ctx.strokeStyle = col;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cp.x, cp.y);
      ctx.lineTo(cp.x, cp.y - 84);
      ctx.stroke();

      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.moveTo(cp.x, cp.y - 84);
      ctx.lineTo(cp.x + 28, cp.y - 72);
      ctx.lineTo(cp.x, cp.y - 60);
      ctx.closePath();
      ctx.fill();
    }

    if (world.config.finishX !== null) {
      const fx = world.config.finishX;
      // Locate ground under finishX roughly from nearest point
      const near = world.points.reduce((best, p) => (Math.abs(p.x - fx) < Math.abs(best.x - fx) ? p : best), world.points[0]!);
      const fy = near ? near.y : 360;
      ctx.fillStyle = "#f472b6";
      ctx.fillRect(fx - 6, fy - 140, 12, 140);
      ctx.fillStyle = "#22d3ee";
      ctx.fillRect(fx + 52, fy - 140, 12, 140);

      ctx.fillStyle = "#0f172a";
      ctx.fillRect(fx - 8, fy - 140, 74, 34);
      ctx.strokeStyle = Math.sin(elapsedSec * 6) > 0 ? "#facc15" : "#22d3ee";
      ctx.lineWidth = 3;
      ctx.strokeRect(fx - 8, fy - 140, 74, 34);
      ctx.fillStyle = "#f8fafc";
      ctx.font = "bold 12px monospace";
      ctx.textAlign = "center";
      ctx.fillText("FINISH", fx + 29, fy - 119);
      ctx.textAlign = "left";
    }
  }

  private drawGhostBike(
    ctx: CanvasRenderingContext2D,
    ghost: GhostSample,
    colors: (typeof LIVERIES)[BikeLiveryId],
  ): void {
    ctx.save();
    ctx.globalAlpha = 0.34;
    ctx.translate(ghost.x, ghost.y);
    ctx.rotate(ghost.angle);
    ctx.strokeStyle = colors.rim;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(-32, 14, WHEEL_RADIUS, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(32, 14, WHEEL_RADIUS, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-32, 14);
    ctx.lineTo(-4, -8);
    ctx.lineTo(18, -10);
    ctx.lineTo(32, 14);
    ctx.stroke();
    ctx.restore();
  }

  private drawBikeAndRider(
    ctx: CanvasRenderingContext2D,
    bike: BikeState,
    settings: GameSettings,
    elapsedSec: number,
  ): void {
    const colors = liveryColors(settings.livery);
    const { rear, front } = getWheelWorldPositions(bike);

    // Subtle ground shadow when close to ground
    if (bike.rearContact.grounded || bike.frontContact.grounded) {
      const groundY = bike.rearContact.grounded ? bike.rearContact.groundY : bike.frontContact.groundY;
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      ctx.beginPath();
      ctx.ellipse(bike.x, groundY + 2, 36, 5, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // Tunnel Headlight Cone
    if (bike.inTunnel || settings.timeOfDay === "night") {
      ctx.save();
      ctx.translate(bike.x + Math.cos(bike.angle) * 26, bike.y + Math.sin(bike.angle) * 26 - 8);
      ctx.rotate(bike.angle);
      const cone = ctx.createRadialGradient(0, 0, 8, 220, 0, 240);
      cone.addColorStop(0, bike.inTunnel ? "rgba(224, 242, 254, 0.42)" : "rgba(56, 189, 248, 0.2)");
      cone.addColorStop(1, "rgba(56, 189, 248, 0)");
      ctx.fillStyle = cone;
      ctx.beginPath();
      ctx.moveTo(0, -4);
      ctx.lineTo(290, -76);
      ctx.lineTo(290, 76);
      ctx.lineTo(0, 4);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    // Draw Wheels
    this.drawWheel(ctx, rear.x, rear.y, bike.rearWheelAngle, colors, !settings.lowQuality);
    this.drawWheel(ctx, front.x, front.y, bike.frontWheelAngle, colors, !settings.lowQuality);

    // Chassis + Fork Compression + Articulated Cyclist
    const rearComp = bike.rearContact.compression * 6;
    const frontComp = bike.frontContact.compression * 7;

    ctx.save();
    ctx.translate(bike.x, bike.y + (bike.crashed ? 6 : 0));
    ctx.rotate(bike.angle);

    // Frame Geometry
    const bbX = -2;
    const bbY = 8 + rearComp * 0.4;
    const seatTopX = -14;
    const seatTopY = -10 + rearComp * 0.45;
    const headTopX = 18;
    const headTopY = -12 + frontComp * 0.5;

    ctx.strokeStyle = colors.frame;
    ctx.lineWidth = 4.2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    if (!settings.lowQuality) {
      ctx.shadowColor = colors.glow;
      ctx.shadowBlur = 10;
    }
    ctx.beginPath();
    ctx.moveTo(-32, 14); // Rear hub
    ctx.lineTo(seatTopX, seatTopY);
    ctx.lineTo(headTopX, headTopY);
    ctx.lineTo(bbX, bbY);
    ctx.lineTo(-32, 14);
    ctx.moveTo(seatTopX, seatTopY);
    ctx.lineTo(bbX, bbY);
    ctx.stroke();

    // Front Suspension Fork (compresses cleanly on landings!)
    ctx.strokeStyle = colors.fork;
    ctx.lineWidth = 3.8;
    ctx.beginPath();
    ctx.moveTo(headTopX, headTopY - 4);
    ctx.lineTo(32, 14);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Handlebars & Saddle
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(headTopX, headTopY - 4);
    ctx.lineTo(headTopX + 4, headTopY - 12);
    ctx.lineTo(headTopX + 10, headTopY - 12);
    ctx.stroke();

    ctx.fillStyle = "#0f172a";
    ctx.fillRect(seatTopX - 9, seatTopY - 4, 16, 5);

    // Tail LED light
    ctx.fillStyle = bike.brakingHard || bike.crashed ? "#ff2a55" : "#f43f5e";
    ctx.fillRect(seatTopX - 11, seatTopY - 1, 5, 3);

    // Articulated Cyclist
    const hipX = seatTopX + 2;
    const hipY = seatTopY - 5;
    const shoulderX = hipX + 14;
    const shoulderY = hipY - 16;
    const crankX = bbX + Math.cos(bike.pedalPhase) * 8;
    const crankY = bbY + Math.sin(bike.pedalPhase) * 8;
    const kneeX = (hipX + crankX) * 0.5 + 8;
    const kneeY = (hipY + crankY) * 0.5 - 5;

    // Scarf / Neon Ribbon
    const wave = Math.sin(elapsedSec * 12) * 3;
    ctx.strokeStyle = "#f472b6";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(shoulderX - 4, shoulderY + 2);
    ctx.quadraticCurveTo(shoulderX - 16, shoulderY - 3 + wave, shoulderX - 28, shoulderY + 3 - wave);
    ctx.stroke();

    // Leg (hip -> knee -> pedal)
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 4.5;
    ctx.beginPath();
    ctx.moveTo(hipX, hipY);
    ctx.lineTo(kneeX, kneeY);
    ctx.lineTo(crankX, crankY);
    ctx.stroke();

    // Jacket Torso
    ctx.strokeStyle = "#f8fafc";
    ctx.lineWidth = 6.5;
    ctx.beginPath();
    ctx.moveTo(hipX, hipY);
    ctx.lineTo(shoulderX, shoulderY);
    ctx.stroke();

    // Arm (shoulder -> grip)
    ctx.strokeStyle = "#cbd5e1";
    ctx.lineWidth = 3.6;
    ctx.beginPath();
    ctx.moveTo(shoulderX, shoulderY);
    ctx.lineTo(headTopX + 6, headTopY - 11);
    ctx.stroke();

    // Aero Helmet & Neon Visor
    const headX = shoulderX + 5;
    const headY = shoulderY - 8;
    ctx.fillStyle = bike.crashed ? "#ef4444" : "#0f172a";
    ctx.beginPath();
    ctx.arc(headX, headY, 8.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = colors.frame;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = "#22d3ee";
    ctx.fillRect(headX + 2, headY - 3, 6.5, 4);

    ctx.restore();
  }

  private drawWheel(
    ctx: CanvasRenderingContext2D,
    wx: number,
    wy: number,
    angle: number,
    colors: (typeof LIVERIES)[BikeLiveryId],
    glow: boolean,
  ): void {
    ctx.save();
    ctx.translate(wx, wy);
    ctx.rotate(angle);

    // Outer tire
    ctx.strokeStyle = "#090d16";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(0, 0, WHEEL_RADIUS, 0, Math.PI * 2);
    ctx.stroke();

    // Neon rim
    ctx.strokeStyle = colors.rim;
    ctx.lineWidth = 2.4;
    if (glow) {
      ctx.shadowColor = colors.glow;
      ctx.shadowBlur = 7;
    }
    ctx.beginPath();
    ctx.arc(0, 0, WHEEL_RADIUS - 3, 0, Math.PI * 2);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // 4 Spokes
    ctx.strokeStyle = "rgba(226, 232, 240, 0.55)";
    ctx.lineWidth = 1.4;
    for (let i = 0; i < 4; i++) {
      const a = (Math.PI * i) / 4;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * -(WHEEL_RADIUS - 4), Math.sin(a) * -(WHEEL_RADIUS - 4));
      ctx.lineTo(Math.cos(a) * (WHEEL_RADIUS - 4), Math.sin(a) * (WHEEL_RADIUS - 4));
      ctx.stroke();
    }
    ctx.restore();
  }

  private drawWeatherOverlay(
    ctx: CanvasRenderingContext2D,
    w: number,
    h: number,
    bike: BikeState,
    settings: GameSettings,
    elapsedSec: number,
  ): void {
    if (settings.weather === "rain") {
      ctx.strokeStyle = "rgba(186, 230, 253, 0.28)";
      ctx.lineWidth = 1.2;
      const drops = settings.lowQuality ? 32 : 70;
      for (let i = 0; i < drops; i++) {
        const rx = ((i * 97 + elapsedSec * 460) % (w + 100)) - 50;
        const ry = ((i * 53 + elapsedSec * 820) % (h + 60)) - 30;
        ctx.beginPath();
        ctx.moveTo(rx, ry);
        ctx.lineTo(rx - 8, ry + 18);
        ctx.stroke();
      }
    } else if (settings.weather === "neon_fog") {
      const fog = ctx.createLinearGradient(0, h * 0.65, 0, h);
      fog.addColorStop(0, "rgba(15, 23, 42, 0)");
      fog.addColorStop(1, "rgba(139, 92, 246, 0.22)");
      ctx.fillStyle = fog;
      ctx.fillRect(0, h * 0.65, w, h * 0.35);
    }

    // Speed lines at high velocity
    const speed = Math.hypot(bike.vx, bike.vy);
    if (speed > 470 && !settings.reducedMotion && !settings.lowQuality) {
      const intensity = Math.min(0.45, (speed - 470) / 700);
      ctx.strokeStyle = `rgba(34, 211, 238, ${intensity})`;
      ctx.lineWidth = 1.5;
      for (let i = 0; i < 12; i++) {
        const lx = ((i * 131 + elapsedSec * 1200) % w);
        const ly = ((i * 79) % h);
        ctx.beginPath();
        ctx.moveTo(lx, ly);
        ctx.lineTo(lx - 48, ly);
        ctx.stroke();
      }
    }
  }

  private drawMinimap(
    ctx: CanvasRenderingContext2D,
    w: number,
    world: GeneratedWorld,
    bike: BikeState,
  ): void {
    const mapW = Math.min(240, w * 0.34);
    const mapX = w * 0.5 - mapW * 0.5;
    const mapY = 14;
    const totalX = world.config.finishX ?? Math.max(2500, world.proceduralCursorX);
    const minX = -180;
    const span = Math.max(400, totalX - minX);

    ctx.fillStyle = "rgba(8, 13, 28, 0.72)";
    ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(mapX, mapY, mapW, 18, 9);
    ctx.fill();
    ctx.stroke();

    for (const cp of world.checkpoints) {
      const px = mapX + 8 + ((cp.x - minX) / span) * (mapW - 16);
      ctx.fillStyle = cp.triggered ? "#34d399" : "#64748b";
      ctx.fillRect(px - 1, mapY + 4, 2, 10);
    }

    const riderRatio = Math.max(0, Math.min(1, (bike.x - minX) / span));
    const rx = mapX + 8 + riderRatio * (mapW - 16);
    ctx.fillStyle = "#f472b6";
    ctx.beginPath();
    ctx.arc(rx, mapY + 9, 4.5, 0, Math.PI * 2);
    ctx.fill();
  }

  private drawDebugSplines(
    ctx: CanvasRenderingContext2D,
    world: GeneratedWorld,
    viewLeft: number,
    viewRight: number,
  ): void {
    ctx.fillStyle = "#fde047";
    for (const pt of world.points) {
      if (pt.x < viewLeft || pt.x > viewRight || pt.gap) continue;
      ctx.fillRect(pt.x - 2, pt.y - 2, 4, 4);
    }
  }

  private drawDebugHitboxes(ctx: CanvasRenderingContext2D, bike: BikeState): void {
    const { rear, front, helmet } = getWheelWorldPositions(bike);
    ctx.strokeStyle = "#4ade80";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(rear.x, rear.y, WHEEL_RADIUS, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(front.x, front.y, WHEEL_RADIUS, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "#fb7185";
    ctx.beginPath();
    ctx.arc(helmet.x, helmet.y, 9, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function liveryColors(id: BikeLiveryId) {
  return LIVERIES[id] ?? LIVERIES.cyan_pulse;
}

export interface BikeStateWithBrake extends BikeState {
  brakingHard?: boolean;
}
