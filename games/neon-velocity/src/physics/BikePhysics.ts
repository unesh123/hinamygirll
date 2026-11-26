import type { BikeState, InputSnapshot, MedalTier, WheelContact } from "../types/game.ts";
import { SURFACE_TABLE, sampleTerrainAtX, updateMovingPlatforms } from "../terrain/TerrainSystem.ts";
import type { GeneratedWorld } from "../terrain/LevelGenerator.ts";
import { appendProceduralChunks } from "../terrain/LevelGenerator.ts";

export const WHEEL_BASE_HALF = 32;
export const WHEEL_OFFSET_Y = 14;
export const WHEEL_RADIUS = 14;
export const GRAVITY = 1280;

export interface PhysicsEvents {
  jumped: boolean;
  landedImpulse: number;
  crashed: boolean;
  checkpointIndex: number | null;
  collectedKind: "cell" | "star" | null;
  brokePropKind: "crate" | "barrier" | "cone" | null;
  finished: boolean;
  stuntAwarded: string | null;
  brakingHard: boolean;
}

function defaultContact(): WheelContact {
  return {
    grounded: false,
    surface: "asphalt",
    normal: { x: 0, y: -1 },
    groundY: 99999,
    grip: 1,
    drag: 0.08,
    compression: 0,
    inTunnel: false,
  };
}

export function createBikeState(startX = 40, startY = 300): BikeState {
  return {
    x: startX,
    y: startY,
    vx: 0,
    vy: 0,
    angle: 0,
    angularVel: 0,
    rearWheelAngle: 0,
    frontWheelAngle: 0,
    rearContact: defaultContact(),
    frontContact: defaultContact(),
    airTime: 0,
    wheelieTime: 0,
    stoppieTime: 0,
    cumulativeAirSpin: 0,
    stuntMessage: "",
    stuntTimer: 0,
    boostEnergy: 100,
    isBoosting: false,
    inTunnel: false,
    pedalPhase: 0,
    crashed: false,
    crashTimer: 0,
    finished: false,
    landingImpulse: 0,
    score: 0,
    flipsDone: 0,
    comboCount: 0,
    comboTimer: 0,
  };
}

export function getWheelWorldPositions(bike: BikeState): {
  rear: { x: number; y: number };
  front: { x: number; y: number };
  helmet: { x: number; y: number };
} {
  const c = Math.cos(bike.angle);
  const s = Math.sin(bike.angle);
  const rear = {
    x: bike.x + -WHEEL_BASE_HALF * c - WHEEL_OFFSET_Y * s,
    y: bike.y + -WHEEL_BASE_HALF * s + WHEEL_OFFSET_Y * c,
  };
  const front = {
    x: bike.x + WHEEL_BASE_HALF * c - WHEEL_OFFSET_Y * s,
    y: bike.y + WHEEL_BASE_HALF * s + WHEEL_OFFSET_Y * c,
  };
  const helmet = {
    x: bike.x + 4 * c - -28 * s,
    y: bike.y + 4 * s + -28 * c,
  };
  return { rear, front, helmet };
}

export function normalizeAngleRad(a: number): number {
  let res = a % (Math.PI * 2);
  if (res > Math.PI) res -= Math.PI * 2;
  if (res < -Math.PI) res += Math.PI * 2;
  return res;
}

export function computeMedal(world: GeneratedWorld, elapsedSec: number, score: number): MedalTier {
  const cfg = world.config;
  if (cfg.finishX === null) {
    if (score >= 4500) return "gold";
    if (score >= 2200) return "silver";
    if (score >= 900) return "bronze";
    return "none";
  }
  if (elapsedSec <= cfg.goldSeconds) return "gold";
  if (elapsedSec <= cfg.silverSeconds) return "silver";
  if (elapsedSec <= cfg.bronzeSeconds) return "bronze";
  return "none";
}

export function stepBikePhysics(
  bike: BikeState,
  world: GeneratedWorld,
  input: InputSnapshot,
  dt: number,
  elapsedSec: number,
  activeCheckpointPos: { x: number; y: number },
): PhysicsEvents {
  const events: PhysicsEvents = {
    jumped: false,
    landedImpulse: 0,
    crashed: false,
    checkpointIndex: null,
    collectedKind: null,
    brokePropKind: null,
    finished: false,
    stuntAwarded: null,
    brakingHard: false,
  };

  if (bike.stuntTimer > 0) bike.stuntTimer = Math.max(0, bike.stuntTimer - dt);
  if (bike.comboTimer > 0) {
    bike.comboTimer = Math.max(0, bike.comboTimer - dt);
    if (bike.comboTimer === 0) bike.comboCount = 0;
  }
  bike.landingImpulse = 0;
  bike.brakingHard = false;

  if (bike.crashed) {
    bike.crashTimer -= dt;
    bike.vx *= Math.pow(0.25, dt);
    bike.vy += GRAVITY * dt;
    bike.x += bike.vx * dt;
    bike.y += bike.vy * dt;
    if (bike.crashTimer <= 0) {
      respawnAtCheckpoint(bike, activeCheckpointPos);
    }
    return events;
  }

  if (bike.finished) {
    bike.vx *= Math.pow(0.18, dt);
    bike.vy += GRAVITY * dt;
    const ground = sampleTerrainAtX(world.points, bike.x, world.platforms, bike.y + WHEEL_OFFSET_Y + WHEEL_RADIUS);
    const maxY = ground.exists ? ground.y - WHEEL_OFFSET_Y - WHEEL_RADIUS : bike.y + 40;
    bike.x += bike.vx * dt;
    bike.y = Math.min(maxY, bike.y + bike.vy * dt);
    if (bike.y >= maxY) bike.vy = 0;
    bike.angularVel *= 0.85;
    bike.angle = normalizeAngleRad(bike.angle) * 0.9;
    return events;
  }

  // Update endless skyline terrain frontier dynamically
  if (world.config.mode === "free_ride" && bike.x > world.proceduralCursorX - 2400) {
    appendProceduralChunks(world, 3);
  }

  const platformVel = updateMovingPlatforms(world.platforms, elapsedSec);

  // Gravity & air drag
  bike.vy += GRAVITY * dt;
  bike.vx *= Math.pow(0.965, dt);
  bike.vy *= Math.pow(0.985, dt);

  const wasGrounded = bike.rearContact.grounded || bike.frontContact.grounded;
  const { rear, front, helmet } = getWheelWorldPositions(bike);

  const solveWheel = (
    wx: number,
    wy: number,
    isRear: boolean,
    contactOut: WheelContact,
  ): number => {
    const sample = sampleTerrainAtX(world.points, wx, world.platforms, wy + WHEEL_RADIUS);
    contactOut.inTunnel = sample.inTunnel;
    if (!sample.exists) {
      contactOut.grounded = false;
      contactOut.compression = 0;
      return 0;
    }

    const wheelBottom = wy + WHEEL_RADIUS;
    const pen = wheelBottom - sample.y;
    contactOut.groundY = sample.y;
    contactOut.normal = { x: sample.normalX, y: sample.normalY };
    contactOut.surface = sample.surface;

    const stats = SURFACE_TABLE[sample.surface];
    contactOut.grip = stats.grip;
    contactOut.drag = stats.drag;

    if (pen < 0 || pen > 95) {
      contactOut.grounded = false;
      contactOut.compression = 0;
      return 0;
    }

    contactOut.grounded = true;
    const clampedPen = Math.min(24, pen);
    contactOut.compression = Math.min(1, clampedPen / 16);

    // Wheel lever arm relative to bike center
    const rx = wx - bike.x;
    const ry = wy - bike.y;
    const pointVx = bike.vx - bike.angularVel * ry;
    const pointVy = bike.vy + bike.angularVel * rx;

    const vn = pointVx * sample.normalX + pointVy * sample.normalY;
    const springK = 195;
    const damperC = 24;
    const springAcc = Math.max(0, clampedPen * springK - vn * damperC);

    // Direct position projection for stability on steep drops & stairs
    const correct = Math.max(0, pen - 0.5) * 0.42;
    bike.x += sample.normalX * correct * 0.5;
    bike.y += sample.normalY * correct;

    bike.vx += sample.normalX * springAcc * dt;
    bike.vy += sample.normalY * springAcc * dt;

    // Torque from off-center suspension push produces organic wheelies, stoppies & pitch compliance
    const torque = rx * (sample.normalY * springAcc) - ry * (sample.normalX * springAcc);
    bike.angularVel += torque * 0.00052 * dt;

    // Match moving platform horizontal drift if standing on one
    for (const plat of world.platforms) {
      if (wx >= plat.x && wx <= plat.x + plat.width && Math.abs(sample.y - plat.y) < 3) {
        const pv = platformVel.get(plat.id);
        if (pv) {
          bike.x += pv.vx;
          bike.y += pv.vy;
        }
      }
    }

    // Terrain tangent
    const tx = -sample.normalY;
    const ty = sample.normalX;
    const speedAlong = bike.vx * tx + bike.vy * ty;

    // Drivetrain / Braking
    if (isRear && input.throttle > 0) {
      const accel = (bike.isBoosting ? 1220 : 760) * stats.grip * input.throttle;
      const topSpeed = bike.isBoosting ? 840 : 560;
      if (speedAlong < topSpeed) {
        bike.vx += tx * accel * dt;
        bike.vy += ty * accel * dt;
      }
    }

    if (input.brake > 0) {
      const decel = 920 * stats.grip * input.brake;
      if (speedAlong > 24) {
        bike.vx -= tx * decel * dt;
        bike.vy -= ty * decel * dt;
        if (speedAlong > 140) events.brakingHard = true;
      } else if (speedAlong > -150) {
        bike.vx -= tx * 340 * input.brake * dt;
        bike.vy -= ty * 340 * input.brake * dt;
      }
    }

    // Rolling drag + surface micro-bumpiness
    const rollingDrag = stats.drag * speedAlong;
    bike.vx -= tx * rollingDrag * dt;
    bike.vy -= ty * rollingDrag * dt;

    if (stats.bumpiness > 0 && Math.abs(speedAlong) > 85) {
      const chatter = Math.sin(wx * 0.19) * stats.bumpiness * Math.min(260, Math.abs(speedAlong)) * 0.6;
      bike.vy -= Math.abs(chatter) * 0.14 * dt * 60;
    }

    return Math.max(0, -vn);
  };

  const rearImpact = solveWheel(rear.x, rear.y, true, bike.rearContact);
  const frontImpact = solveWheel(front.x, front.y, false, bike.frontContact);
  const groundedNow = bike.rearContact.grounded || bike.frontContact.grounded;
  bike.inTunnel = bike.rearContact.inTunnel || bike.frontContact.inTunnel;

  // Tunnel low-roof ceiling clamp
  const surfSample = sampleTerrainAtX(world.points, bike.x, world.platforms, bike.y);
  if (surfSample.inTunnel && surfSample.tunnelRoofY !== null && helmet.y < surfSample.tunnelRoofY + 6) {
    const pushDown = surfSample.tunnelRoofY + 6 - helmet.y;
    bike.y += pushDown;
    bike.vy = Math.max(0, bike.vy * -0.2);
  }

  // Nitro Boost
  const wantsBoost = input.boost && bike.boostEnergy > 4;
  bike.isBoosting = wantsBoost;
  if (wantsBoost) {
    bike.boostEnergy = Math.max(0, bike.boostEnergy - 32 * dt);
    if (groundedNow) {
      const fx = Math.cos(bike.angle);
      const fy = Math.sin(bike.angle);
      bike.vx += fx * 420 * dt;
      bike.vy += fy * 420 * dt;
    } else {
      bike.vx += 180 * dt;
    }
  } else {
    bike.boostEnergy = Math.min(100, bike.boostEnergy + (groundedNow ? 10 : 4) * dt);
  }

  // Bunny Hop / Jump
  if (input.jumpPressed && (groundedNow || bike.airTime < 0.09)) {
    bike.vy = Math.min(bike.vy, 0) - 435;
    bike.y -= 5;
    bike.rearContact.grounded = false;
    bike.frontContact.grounded = false;
    events.jumped = true;
  }

  // Rider Lean / Wheelie / Air Flip Torque
  if (groundedNow) {
    const torqueAccel = input.lean * 11.5;
    bike.angularVel += torqueAccel * dt;
    // Gentle self-leveling damping when both wheels are down
    if (bike.rearContact.grounded && bike.frontContact.grounded) {
      const avgNormalX = (bike.rearContact.normal.x + bike.frontContact.normal.x) * 0.5;
      const avgNormalY = (bike.rearContact.normal.y + bike.frontContact.normal.y) * 0.5;
      const desiredAngle = Math.atan2(-avgNormalX, -avgNormalY);
      const diff = normalizeAngleRad(desiredAngle - bike.angle);
      bike.angularVel += diff * 18 * dt;
      bike.angularVel *= Math.pow(0.08, dt);
    } else {
      // Single-wheel wheelie or stoppie balance zone!
      bike.angularVel *= Math.pow(0.32, dt);
    }
  } else {
    // Crisp airborne rotation for flips
    bike.angularVel += input.lean * 12.8 * dt;
    bike.angularVel *= Math.pow(0.45, dt);
  }

  const maxAngVel = 7.6;
  bike.angularVel = Math.max(-maxAngVel, Math.min(maxAngVel, bike.angularVel));

  // Integrate kinematics
  bike.x += bike.vx * dt;
  bike.y += bike.vy * dt;
  const dAngle = bike.angularVel * dt;
  bike.angle += dAngle;

  // Spin wheels & rider cadence
  const wheelSpinRate = (bike.vx / WHEEL_RADIUS) * dt;
  bike.rearWheelAngle += wheelSpinRate;
  bike.frontWheelAngle += wheelSpinRate;
  if (input.throttle > 0 && bike.rearContact.grounded) {
    bike.pedalPhase += dt * (7 + Math.min(12, Math.abs(bike.vx) / 36));
  } else {
    bike.pedalPhase += dt * Math.min(4, Math.abs(bike.vx) / 140);
  }

  // Air vs Landing trick detection
  if (!groundedNow) {
    bike.airTime += dt;
    bike.cumulativeAirSpin += dAngle;
    bike.wheelieTime = 0;
    bike.stoppieTime = 0;
  } else {
    if (!wasGrounded) {
      const impact = Math.max(rearImpact, frontImpact);
      bike.landingImpulse = impact;
      events.landedImpulse = impact;

      const absSpin = Math.abs(bike.cumulativeAirSpin);
      if (absSpin >= Math.PI * 1.55) {
        const flips = Math.max(1, Math.round(absSpin / (Math.PI * 2)));
        bike.flipsDone += flips;
        bike.comboCount += flips;
        bike.comboTimer = 3.5;
        const pts = flips * 350 * Math.min(4, bike.comboCount);
        bike.score += pts;
        bike.boostEnergy = Math.min(100, bike.boostEnergy + flips * 26);
        const dir = bike.cumulativeAirSpin < 0 ? "BACKFLIP" : "FRONTFLIP";
        const label = flips > 1 ? `${flips}x ${dir} +${pts}` : `${dir} +${pts}`;
        bike.stuntMessage = label;
        bike.stuntTimer = 1.65;
        events.stuntAwarded = label;
      } else if (bike.airTime > 0.7) {
        const airPts = Math.round(bike.airTime * 110);
        bike.score += airPts;
        bike.boostEnergy = Math.min(100, bike.boostEnergy + 12);
        events.stuntAwarded = `BIG AIR +${airPts}`;
        bike.stuntMessage = events.stuntAwarded;
        bike.stuntTimer = 1.25;
      }
      bike.cumulativeAirSpin = 0;
    }
    bike.airTime = 0;

    // Sustained Wheelie / Stoppie scoring
    const normAng = normalizeAngleRad(bike.angle);
    if (bike.rearContact.grounded && !bike.frontContact.grounded && normAng < -0.22 && Math.abs(bike.vx) > 90) {
      bike.wheelieTime += dt;
      bike.score += dt * 75;
      if (bike.wheelieTime > 0.65 && bike.stuntTimer <= 0.1) {
        bike.stuntMessage = `WHEELIE ${bike.wheelieTime.toFixed(1)}s`;
        bike.stuntTimer = 0.5;
      }
    } else if (bike.frontContact.grounded && !bike.rearContact.grounded && normAng > 0.22 && Math.abs(bike.vx) > 70) {
      bike.stoppieTime += dt;
      bike.score += dt * 85;
      if (bike.stoppieTime > 0.5 && bike.stuntTimer <= 0.1) {
        bike.stuntMessage = `STOPPIE ${bike.stoppieTime.toFixed(1)}s`;
        bike.stuntTimer = 0.5;
      }
    }
  }

  // Head / Helmet crash detection against terrain + steep nose-plant + abyss drop
  const updatedPos = getWheelWorldPositions(bike);
  const headGround = sampleTerrainAtX(world.points, updatedPos.helmet.x, world.platforms, updatedPos.helmet.y + 8);
  const absNormAngle = Math.abs(normalizeAngleRad(bike.angle));
  const headSlam = headGround.exists && updatedPos.helmet.y + 8 > headGround.y && absNormAngle > 1.32;
  const hardRoofCrash = absNormAngle > 1.82 && groundedNow;
  const fellInChasm = bike.y > world.config.fallY;

  if (headSlam || hardRoofCrash || fellInChasm) {
    bike.crashed = true;
    bike.crashTimer = 1.05;
    events.crashed = true;
    return events;
  }

  // Hazard checks
  for (const haz of world.hazards) {
    if (
      bike.x + 18 > haz.x &&
      bike.x - 18 < haz.x + haz.width &&
      bike.y + WHEEL_OFFSET_Y + WHEEL_RADIUS > haz.y &&
      bike.y - 16 < haz.y + haz.height
    ) {
      bike.crashed = true;
      bike.crashTimer = 1.05;
      events.crashed = true;
      return events;
    }
  }

  // Breakable Props
  for (const prop of world.props) {
    if (prop.broken) continue;
    if (
      bike.x + 30 > prop.x &&
      bike.x - 30 < prop.x + prop.width &&
      bike.y + 24 > prop.y &&
      bike.y - 24 < prop.y + prop.height
    ) {
      prop.broken = true;
      prop.breakTimer = 1.0;
      events.brokePropKind = prop.kind;
      if (!bike.isBoosting) {
        bike.vx *= prop.kind === "barrier" ? 0.78 : prop.kind === "crate" ? 0.88 : 0.96;
      }
      const bonus = prop.kind === "barrier" ? 120 : prop.kind === "crate" ? 80 : 40;
      bike.score += bonus;
      bike.stuntMessage = `SMASH +${bonus}`;
      bike.stuntTimer = 0.8;
    }
  }

  // Collectibles
  for (const col of world.collectibles) {
    if (col.collected) continue;
    const dist = Math.hypot(bike.x - col.x, bike.y - col.y);
    if (dist <= 38) {
      col.collected = true;
      events.collectedKind = col.kind;
      const pts = col.kind === "star" ? 250 : 100;
      bike.score += pts;
      bike.boostEnergy = Math.min(100, bike.boostEnergy + (col.kind === "star" ? 32 : 18));
      bike.stuntMessage = col.kind === "star" ? `STYLE STAR +${pts}` : `ENERGY CELL +${pts}`;
      bike.stuntTimer = 0.85;
    }
  }

  // Checkpoints
  for (const cp of world.checkpoints) {
    if (!cp.triggered && bike.x >= cp.x - 16) {
      cp.triggered = true;
      events.checkpointIndex = cp.index;
      bike.score += 150;
      bike.boostEnergy = Math.min(100, bike.boostEnergy + 20);
    }
  }

  // Finish Gate
  if (world.config.finishX !== null && bike.x >= world.config.finishX) {
    bike.finished = true;
    events.finished = true;
  }

  // Distance trickle score
  if (bike.vx > 80) {
    bike.score += (bike.vx * dt) * 0.08;
  }
  bike.brakingHard = events.brakingHard;

  return events;
}

export function respawnAtCheckpoint(bike: BikeState, checkpoint: { x: number; y: number }): void {
  bike.x = checkpoint.x;
  bike.y = checkpoint.y - 42;
  bike.vx = 0;
  bike.vy = 0;
  bike.angle = 0;
  bike.angularVel = 0;
  bike.cumulativeAirSpin = 0;
  bike.airTime = 0;
  bike.wheelieTime = 0;
  bike.stoppieTime = 0;
  bike.crashed = false;
  bike.crashTimer = 0;
  bike.isBoosting = false;
  bike.boostEnergy = Math.max(bike.boostEnergy, 65);
  bike.rearContact = defaultContact();
  bike.frontContact = defaultContact();
}
