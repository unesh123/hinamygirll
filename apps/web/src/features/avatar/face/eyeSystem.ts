import { clamp01, type ArkitWeights } from "./arkit";
import type { EmotionName } from "./expressionMixer";

/** Blink cadence bounds (seconds) at rate 1. Human mean ≈ 4 s, range 1.5–7 s. */
export const BLINK_INTERVAL_MIN = 1.8;
export const BLINK_INTERVAL_MAX = 6;
/** Normalised gaze units (±1 = full eye travel). */
export const SACCADE_MAX_AMPLITUDE = 0.35;
export const MICRO_SACCADE_MAX_AMPLITUDE = 0.04;

export type GazeMode = "camera" | "away" | "down";

export interface EyeContext {
  gazeMode: GazeMode;
  /** Blink-rate multiplier (0.5–2.5). */
  blinkRate: number;
  /** Scales saccade size/frequency (0 freezes eyes, 1 = normal). */
  saccadeScale: number;
  /** 0..1 resting lid closure (sleepiness). */
  lidDroop: number;
}

export const NEUTRAL_EYE_CONTEXT: EyeContext = { gazeMode: "camera", blinkRate: 1, saccadeScale: 1, lidDroop: 0 };

export function nextBlinkInterval(rng: () => number, rate = 1): number {
  const r = Math.max(0.5, Math.min(2.5, rate));
  return (BLINK_INTERVAL_MIN + rng() * (BLINK_INTERVAL_MAX - BLINK_INTERVAL_MIN)) / r;
}

/** Random saccade target offset with bounded amplitude (radial). */
export function sampleSaccade(rng: () => number, maxAmplitude = SACCADE_MAX_AMPLITUDE): { x: number; y: number } {
  const amp = maxAmplitude * Math.sqrt(rng());
  const ang = rng() * Math.PI * 2;
  // Eyes travel less vertically than horizontally.
  return { x: Math.cos(ang) * amp, y: Math.sin(ang) * amp * 0.6 };
}

/** Derive eye behaviour from the dominant emotion and conversational state. */
export function eyeContextFor(
  emotions: Partial<Record<EmotionName, number>>,
  state: { thinking?: boolean; speaking?: boolean; listening?: boolean },
): EyeContext {
  const e = (n: EmotionName) => emotions[n] ?? 0;
  let gazeMode: GazeMode = "camera";
  if (state.thinking || e("thinking") > 0.45) gazeMode = "away";
  else if (e("shy") > 0.4 || e("sorrow") > 0.5 || e("sleepy") > 0.5) gazeMode = "down";
  const blinkRate = clamp(1 + e("shy") * 0.5 + e("fear") * 0.5 + (state.thinking ? 0.2 : 0) - e("anger") * 0.3 - e("sleepy") * 0.4
    - (state.listening ? 0.1 : 0), 0.5, 2.5);
  const saccadeScale = clamp(1 - e("anger") * 0.5 - e("sleepy") * 0.4 + e("fear") * 0.5 + e("surprise") * 0.2, 0.2, 1.6);
  return { gazeMode, blinkRate, saccadeScale, lidDroop: clamp01(e("sleepy") * 0.45) };
}

const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);

export interface EyeFrame {
  /** +x = subject's right, +y = up. Range ±1. */
  gazeX: number;
  gazeY: number;
  /** Combined lid closure incl. droop and gaze-follow, 0..1. */
  blink: number;
  blinkLeft: number;
  blinkRight: number;
  arkit: ArkitWeights;
}

const BLINK_CLOSE = 0.07;
const BLINK_HOLD = 0.03;
const BLINK_OPEN = 0.16;

export class EyeSystem {
  private rng: () => number;
  private blinkTimer: number;
  private blinkT = -1;
  private pendingDouble = false;
  private saccadeTimer = 0.6;
  private microTimer = 0.2;
  private target = { x: 0, y: 0 };
  private micro = { x: 0, y: 0 };
  private gaze = { x: 0, y: 0 };
  private awayTimer = 0;
  private awayDir = { x: -0.18, y: 0.14 };
  private frame: EyeFrame = { gazeX: 0, gazeY: 0, blink: 0, blinkLeft: 0, blinkRight: 0, arkit: {} };

  constructor(rng: () => number = Math.random) {
    this.rng = rng;
    this.blinkTimer = nextBlinkInterval(rng);
  }

  /** Blink 0..1 curve value for time since blink start. */
  static blinkCurve(t: number): number {
    if (t < 0) return 0;
    if (t < BLINK_CLOSE) return t / BLINK_CLOSE;
    if (t < BLINK_CLOSE + BLINK_HOLD) return 1;
    const o = (t - BLINK_CLOSE - BLINK_HOLD) / BLINK_OPEN;
    return o >= 1 ? 0 : 1 - o * o * (3 - 2 * o);
  }

  startBlink(): void { this.blinkT = 0; }

  private anchor(ctx: EyeContext, dt: number): { x: number; y: number } {
    if (ctx.gazeMode === "away") {
      this.awayTimer -= dt;
      if (this.awayTimer <= 0) {
        // Break eye contact for a while, then glance back briefly.
        const away = this.target.x === 0 || this.awayTimer < -1.2;
        this.awayTimer = away ? 1.6 + this.rng() * 1.6 : -2;
        this.awayDir = { x: (this.rng() < 0.65 ? -1 : 1) * (0.12 + this.rng() * 0.12), y: 0.06 + this.rng() * 0.12 };
      }
      return this.awayTimer > 0 ? this.awayDir : { x: 0, y: 0 };
    }
    if (ctx.gazeMode === "down") return { x: -0.05, y: -0.2 };
    return { x: 0, y: 0 };
  }

  update(dt: number, ctx: EyeContext = NEUTRAL_EYE_CONTEXT): EyeFrame {
    dt = Math.max(0, Math.min(dt, 0.1));
    const rng = this.rng;
    const anchor = this.anchor(ctx, dt);

    // Saccades: ballistic jumps around the anchor.
    this.saccadeTimer -= dt;
    if (this.saccadeTimer <= 0) {
      const s = sampleSaccade(rng, SACCADE_MAX_AMPLITUDE * Math.min(1, ctx.saccadeScale));
      this.target = { x: anchor.x + s.x * 0.6, y: anchor.y + s.y * 0.6 };
      this.saccadeTimer = (0.5 + rng() * 2.2) / Math.max(0.3, ctx.saccadeScale);
      if (Math.hypot(s.x, s.y) > 0.2 && this.blinkT < 0 && rng() < 0.45) this.blinkT = 0;
    }
    // Micro-saccades: tiny fixational jitter.
    this.microTimer -= dt;
    if (this.microTimer <= 0) {
      const m = sampleSaccade(rng, MICRO_SACCADE_MAX_AMPLITUDE * Math.min(1.5, ctx.saccadeScale));
      this.micro = m;
      this.microTimer = 0.1 + rng() * 0.35;
    }
    // Anchor shifts (e.g. look-away) also pull the target.
    this.target.x += (anchor.x - this.target.x) * Math.min(1, dt * 0.6);
    this.target.y += (anchor.y - this.target.y) * Math.min(1, dt * 0.6);

    const k = 1 - Math.exp(-dt * 38);
    this.gaze.x += (this.target.x + this.micro.x - this.gaze.x) * k;
    this.gaze.y += (this.target.y + this.micro.y - this.gaze.y) * k;

    // Blink.
    if (this.blinkT >= 0) {
      this.blinkT += dt;
      if (this.blinkT > BLINK_CLOSE + BLINK_HOLD + BLINK_OPEN) {
        this.blinkT = -1;
        if (this.pendingDouble) {
          this.pendingDouble = false;
          this.blinkT = 0;
        }
      }
    } else {
      this.blinkTimer -= dt;
      if (this.blinkTimer <= 0) {
        this.blinkT = 0;
        this.pendingDouble = rng() < 0.1;
        this.blinkTimer = nextBlinkInterval(rng, ctx.blinkRate);
      }
    }
    const blinkCurve = EyeSystem.blinkCurve(this.blinkT);

    // Eyelids track gaze: lids lower when looking down and lift when looking up.
    const follow = -this.gaze.y * 0.35;
    const baseLid = clamp01(ctx.lidDroop + Math.max(0, follow));
    const wide = Math.max(0, -follow) * 0.6;
    const lid = clamp01(baseLid + (1 - baseLid) * blinkCurve);
    const f = this.frame;
    f.gazeX = this.gaze.x;
    f.gazeY = this.gaze.y;
    f.blink = lid;
    // Left eye starts closing a hair earlier than the right.
    f.blinkLeft = clamp01(lid + (blinkCurve > 0 && blinkCurve < 1 ? 0.04 : 0));
    f.blinkRight = clamp01(lid - (blinkCurve > 0 && blinkCurve < 1 ? 0.04 : 0));

    const x = this.gaze.x;
    const y = this.gaze.y;
    const a = f.arkit;
    const up = clamp01(y);
    const down = clamp01(-y);
    const toRight = clamp01(x);
    const toLeft = clamp01(-x);
    a.eyeLookUpLeft = up;
    a.eyeLookUpRight = up;
    a.eyeLookDownLeft = down;
    a.eyeLookDownRight = down;
    a.eyeLookInLeft = toRight;
    a.eyeLookOutRight = toRight;
    a.eyeLookOutLeft = toLeft;
    a.eyeLookInRight = toLeft;
    a.eyeBlinkLeft = f.blinkLeft;
    a.eyeBlinkRight = f.blinkRight;
    a.eyeWideLeft = wide * (1 - blinkCurve);
    a.eyeWideRight = wide * (1 - blinkCurve);
    return f;
  }
}
