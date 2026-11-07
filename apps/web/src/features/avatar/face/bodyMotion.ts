export interface BodyPose {
  /** Radians, added on top of the rest pose. */
  chestPitch: number;
  spinePitch: number;
  spineRoll: number;
  headPitch: number;
  headYaw: number;
  headRoll: number;
  shoulderLeft: number;
  shoulderRight: number;
  /** Metres. */
  hipsX: number;
  hipsRoll: number;
  /** Chest scale multiplier from breathing. */
  chestScale: number;
}

export interface BodyContext {
  speaking: boolean;
  /** Smoothed speech loudness 0..1. */
  energy: number;
  /** 0..1, calms breathing and sway when low. */
  arousal?: number;
  reducedMotion?: boolean;
}

const EMPHASIS_THRESHOLD = 0.55;
const NOD_COOLDOWN = 0.9;
const NOD_DURATION = 0.45;

/** Procedural idle + conversation body language. Pure: no three.js dependency. */
export class BodyMotion {
  private t = 0;
  private nodT = -1;
  private nodAmp = 0;
  private cooldown = 0;
  private prevEnergy = 0;
  private shiftFrom = 0;
  private shiftTo = 0;
  private shiftT = 1;
  private shiftTimer = 4;
  private rng: () => number;
  private pose: BodyPose = {
    chestPitch: 0, spinePitch: 0, spineRoll: 0, headPitch: 0, headYaw: 0, headRoll: 0,
    shoulderLeft: 0, shoulderRight: 0, hipsX: 0, hipsRoll: 0, chestScale: 1,
  };

  constructor(rng: () => number = Math.random) { this.rng = rng; }

  triggerNod(amplitude = 0.08): void {
    this.nodT = 0;
    this.nodAmp = Math.min(0.14, Math.max(0, amplitude));
  }

  update(dt: number, ctx: BodyContext): BodyPose {
    dt = Math.max(0, Math.min(dt, 0.1));
    this.t += dt;
    this.cooldown -= dt;
    const calm = ctx.reducedMotion ? 0.25 : 1;
    const arousal = ctx.arousal ?? 0.4;
    const p = this.pose;

    // Emphasis: a loudness onset while speaking nods the head.
    if (ctx.speaking && !ctx.reducedMotion && this.cooldown <= 0
        && ctx.energy > EMPHASIS_THRESHOLD && this.prevEnergy < EMPHASIS_THRESHOLD) {
      this.triggerNod(0.04 + ctx.energy * 0.06);
      this.cooldown = NOD_COOLDOWN;
    }
    this.prevEnergy = ctx.energy;

    let nod = 0;
    if (this.nodT >= 0) {
      this.nodT += dt;
      if (this.nodT >= NOD_DURATION) this.nodT = -1;
      else nod = Math.sin((this.nodT / NOD_DURATION) * Math.PI) * this.nodAmp;
    }

    // Weight shift: a slow lateral transfer every few seconds.
    this.shiftTimer -= dt;
    if (this.shiftTimer <= 0) {
      this.shiftFrom = this.shiftFrom + (this.shiftTo - this.shiftFrom) * Math.min(1, this.shiftT);
      this.shiftTo = (this.rng() * 2 - 1);
      this.shiftT = 0;
      this.shiftTimer = 4 + this.rng() * 6;
    }
    this.shiftT = Math.min(1, this.shiftT + dt / 1.8);
    const e = this.shiftT * this.shiftT * (3 - 2 * this.shiftT);
    const shift = (this.shiftFrom + (this.shiftTo - this.shiftFrom) * e) * calm;

    // Breathing: ~14 cycles/min, faster/deeper with arousal.
    const breathHz = 0.22 + arousal * 0.1;
    const breath = Math.sin(this.t * Math.PI * 2 * breathHz);
    const breathAmp = (0.6 + arousal * 0.6) * calm;

    p.chestScale = 1 + breath * 0.008 * breathAmp;
    p.chestPitch = breath * 0.012 * breathAmp;
    p.spinePitch = breath * 0.006 * breathAmp;
    p.spineRoll = shift * 0.02;
    p.hipsX = shift * 0.012;
    p.hipsRoll = -shift * 0.025;
    // Shoulders rise with the inhale and counter-swing on the weight shift.
    p.shoulderLeft = (breath * 0.012 + shift * 0.01) * breathAmp;
    p.shoulderRight = (breath * 0.012 - shift * 0.01) * breathAmp;
    p.headPitch = nod - breath * 0.004 * breathAmp;
    p.headYaw = Math.sin(this.t * 0.31) * 0.02 * calm;
    p.headRoll = -shift * 0.015 + Math.sin(this.t * 0.23 + 1) * 0.01 * calm;
    return p;
  }
}
