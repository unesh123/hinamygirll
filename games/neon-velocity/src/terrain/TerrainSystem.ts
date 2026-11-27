import type { MovingPlatform, SurfaceStats, SurfaceType, TerrainPoint } from "../types/game.ts";

export const SURFACE_TABLE: Record<SurfaceType, SurfaceStats> = {
  asphalt: {
    grip: 1.0,
    drag: 0.08,
    bumpiness: 0.0,
    restitution: 0.08,
    color: "#1a2238",
    accent: "#22d3ee",
  },
  wood_ramp: {
    grip: 0.96,
    drag: 0.06,
    bumpiness: 0.02,
    restitution: 0.05,
    color: "#4d2f1d",
    accent: "#f97316",
  },
  stairs: {
    grip: 0.85,
    drag: 0.14,
    bumpiness: 0.25,
    restitution: 0.14,
    color: "#2b334e",
    accent: "#a855f7",
  },
  rooftop: {
    grip: 0.98,
    drag: 0.07,
    bumpiness: 0.03,
    restitution: 0.06,
    color: "#1e293b",
    accent: "#ec4899",
  },
  beam: {
    grip: 0.9,
    drag: 0.05,
    bumpiness: 0.04,
    restitution: 0.1,
    color: "#3f2e1d",
    accent: "#facc15",
  },
  dirt: {
    grip: 0.72,
    drag: 0.28,
    bumpiness: 0.18,
    restitution: 0.04,
    color: "#3d281f",
    accent: "#fb923c",
  },
  bridge: {
    grip: 0.94,
    drag: 0.08,
    bumpiness: 0.05,
    restitution: 0.08,
    color: "#193044",
    accent: "#38bdf8",
  },
  tunnel: {
    grip: 1.02,
    drag: 0.06,
    bumpiness: 0.0,
    restitution: 0.05,
    color: "#111629",
    accent: "#818cf8",
  },
};

export interface GroundSample {
  exists: boolean;
  y: number;
  normalX: number;
  normalY: number;
  slope: number;
  surface: SurfaceType;
  inTunnel: boolean;
  tunnelRoofY: number | null;
  platformVx: number;
  platformVy: number;
}

const NO_GROUND: GroundSample = {
  exists: false,
  y: 99999,
  normalX: 0,
  normalY: -1,
  slope: 0,
  surface: "asphalt",
  inTunnel: false,
  tunnelRoofY: null,
  platformVx: 0,
  platformVy: 0,
};

export function sampleTerrainAtX(
  points: TerrainPoint[],
  x: number,
  platforms: MovingPlatform[] = [],
  wheelBottomHintY?: number,
): GroundSample {
  let best = NO_GROUND;

  if (points.length >= 2) {
    let lo = 0;
    let hi = points.length - 2;
    let idx = -1;
    if (x >= points[0]!.x && x <= points[points.length - 1]!.x) {
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const pMid = points[mid]!;
        const pNext = points[mid + 1]!;
        if (x >= pMid.x && x <= pNext.x) {
          idx = mid;
          break;
        }
        if (x < pMid.x) {
          hi = mid - 1;
        } else {
          lo = mid + 1;
        }
      }
    }

    if (idx >= 0) {
      const a = points[idx]!;
      const b = points[idx + 1]!;
      if (!a.gap && !b.gap) {
        const dx = Math.max(1e-5, b.x - a.x);
        const t = Math.max(0, Math.min(1, (x - a.x) / dx));
        const y = a.y + (b.y - a.y) * t;
        const dy = b.y - a.y;
        const len = Math.hypot(dx, dy) || 1;
        // Normal pointing upward in screen coordinates (+y down -> up normal has negative y)
        const normalX = dy / len;
        const normalY = -dx / len;
        const roofA = a.tunnelRoofY ?? null;
        const roofB = b.tunnelRoofY ?? null;
        const roof = roofA !== null && roofB !== null ? roofA + (roofB - roofA) * t : roofA ?? roofB;

        best = {
          exists: true,
          y,
          normalX,
          normalY,
          slope: dy / dx,
          surface: a.surface,
          inTunnel: roof !== null,
          tunnelRoofY: roof,
          platformVx: 0,
          platformVy: 0,
        };
      }
    }
  }

  for (const plat of platforms) {
    if (x >= plat.x && x <= plat.x + plat.width) {
      const canStand = wheelBottomHintY === undefined || wheelBottomHintY <= plat.y + 36;
      if (canStand && (!best.exists || plat.y < best.y)) {
        best = {
          exists: true,
          y: plat.y,
          normalX: 0,
          normalY: -1,
          slope: 0,
          surface: plat.surface,
          inTunnel: best.inTunnel,
          tunnelRoofY: best.tunnelRoofY,
          platformVx: 0,
          platformVy: 0,
        };
      }
    }
  }

  return best;
}

export function updateMovingPlatforms(platforms: MovingPlatform[], elapsedSec: number): Map<string, { vx: number; vy: number }> {
  const velocities = new Map<string, { vx: number; vy: number }>();
  for (const p of platforms) {
    const prevX = p.x;
    const prevY = p.y;
    const angle = elapsedSec * p.speed + p.phase;
    p.x = p.baseX + Math.sin(angle) * p.ampX;
    p.y = p.baseY + Math.sin(angle) * p.ampY;
    velocities.set(p.id, {
      vx: p.x - prevX,
      vy: p.y - prevY,
    });
  }
  return velocities;
}
