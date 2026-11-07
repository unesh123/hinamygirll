import { ARKIT_BLENDSHAPES, clamp01, type ArkitName, type ArkitWeights } from "./arkit";

export const EMOTION_NAMES = [
  "joy", "sorrow", "anger", "surprise", "fear", "disgust",
  "shy", "smug", "thinking", "sleepy", "love", "neutral",
] as const;
export type EmotionName = (typeof EMOTION_NAMES)[number];
export type EmotionWeights = Partial<Record<EmotionName, number>>;

export type VrmPresetKey = "happy" | "angry" | "sad" | "relaxed" | "surprised" | "neutral";
export type VrmPresetWeights = Partial<Record<VrmPresetKey, number>>;

interface EmotionProfile {
  vrm: VrmPresetWeights;
  arkit: ArkitWeights;
}

const both = (base: string, v: number): ArkitWeights =>
  ({ [`${base}Left`]: v, [`${base}Right`]: v }) as ArkitWeights;
const merge = (...parts: ArkitWeights[]): ArkitWeights => Object.assign({}, ...parts);

/** Full-intensity ARKit/VRM target for each emotion. Mixed linearly by weight. */
export const EMOTION_PROFILES: Record<EmotionName, EmotionProfile> = {
  neutral: { vrm: { neutral: 1 }, arkit: {} },
  joy: {
    vrm: { happy: 0.85 },
    arkit: merge(both("mouthSmile", 0.7), both("cheekSquint", 0.45), both("eyeSquint", 0.3),
      both("browOuterUp", 0.12), both("mouthDimple", 0.25), both("mouthUpperUp", 0.12)),
  },
  sorrow: {
    vrm: { sad: 0.85 },
    arkit: merge({ browInnerUp: 0.7 }, both("browDown", 0.1), both("mouthFrown", 0.55),
      both("mouthPress", 0.15), { mouthShrugLower: 0.3, mouthRollLower: 0.1 }, both("eyeLookDown", 0.12)),
  },
  anger: {
    vrm: { angry: 0.85 },
    arkit: merge(both("browDown", 0.8), both("eyeSquint", 0.3), both("noseSneer", 0.4),
      both("mouthPress", 0.4), both("mouthFrown", 0.2), both("eyeWide", 0.1), { jawForward: 0.1 }),
  },
  surprise: {
    vrm: { surprised: 0.85 },
    arkit: merge({ browInnerUp: 0.75, jawOpen: 0.35 }, both("browOuterUp", 0.7), both("eyeWide", 0.75),
      both("mouthUpperUp", 0.1)),
  },
  fear: {
    vrm: { sad: 0.4, surprised: 0.55 },
    arkit: merge({ browInnerUp: 0.85, jawOpen: 0.15 }, both("eyeWide", 0.65), both("browOuterUp", 0.25),
      both("mouthStretch", 0.45), both("mouthFrown", 0.2)),
  },
  disgust: {
    vrm: { angry: 0.4, sad: 0.2 },
    arkit: merge(both("noseSneer", 0.75), both("mouthUpperUp", 0.5), both("eyeSquint", 0.4),
      both("browDown", 0.35), { mouthShrugUpper: 0.25 }, both("mouthFrown", 0.25)),
  },
  shy: {
    vrm: { happy: 0.3, relaxed: 0.35 },
    arkit: merge(both("mouthSmile", 0.3), both("cheekSquint", 0.3), { browInnerUp: 0.3, mouthRollLower: 0.2 },
      both("eyeLookDown", 0.35), both("eyeSquint", 0.12), both("mouthPress", 0.1)),
  },
  smug: {
    vrm: { happy: 0.35, relaxed: 0.3 },
    arkit: merge({ mouthSmileLeft: 0.7, mouthSmileRight: 0.2, browOuterUpLeft: 0.4 }, both("eyeSquint", 0.3),
      { mouthDimpleLeft: 0.3, eyeBlinkLeft: 0.1 }, both("eyeLookDown", 0.08)),
  },
  thinking: {
    vrm: { neutral: 0.5, relaxed: 0.2 },
    arkit: merge({ browInnerUp: 0.2, browOuterUpLeft: 0.35, mouthPucker: 0.15, mouthLeft: 0.2 },
      both("eyeLookUp", 0.2), both("eyeSquint", 0.1)),
  },
  sleepy: {
    vrm: { relaxed: 0.6 },
    arkit: merge(both("browDown", 0.1), { browInnerUp: 0.1, jawOpen: 0.05 },
      both("eyeLookDown", 0.2), both("mouthSmile", 0.08)),
  },
  love: {
    vrm: { happy: 0.6, relaxed: 0.4 },
    arkit: merge(both("mouthSmile", 0.5), both("cheekSquint", 0.4), both("eyeSquint", 0.25),
      { browInnerUp: 0.25 }, both("eyeBlink", 0.12), both("mouthDimple", 0.15)),
  },
};

/**
 * Clamp negatives and keep the sum of non-neutral emotions within `cap`,
 * then let neutral absorb the remainder so the full vector sums to 1.
 */
export function normalizeEmotions(input: EmotionWeights, cap = 1): Record<EmotionName, number> {
  const out = {} as Record<EmotionName, number>;
  let sum = 0;
  for (const name of EMOTION_NAMES) {
    const v = name === "neutral" ? 0 : Math.max(0, input[name] ?? 0);
    out[name] = Number.isFinite(v) ? v : 0;
    sum += out[name];
  }
  const limit = Math.max(0, Math.min(1, cap));
  if (sum > limit && sum > 0) {
    const k = limit / sum;
    for (const name of EMOTION_NAMES) out[name] *= k;
    sum = limit;
  }
  out.neutral = 1 - sum;
  return out;
}

interface MicroExpression {
  arkit: ArkitWeights;
  vrm?: VrmPresetWeights;
  /** seconds */
  duration: [number, number];
  amplitude: [number, number];
  /** Emotions that make this flicker more likely; absent = always eligible. */
  affinity?: EmotionName[];
}

export const MICRO_EXPRESSIONS: MicroExpression[] = [
  { arkit: merge({ browInnerUp: 0.6 }, both("browOuterUp", 0.5)), duration: [0.18, 0.4], amplitude: [0.1, 0.22] },
  { arkit: { mouthSmileLeft: 0.7, mouthDimpleLeft: 0.4 }, vrm: { happy: 0.12 }, duration: [0.25, 0.6], amplitude: [0.08, 0.2], affinity: ["joy", "smug", "love", "shy"] },
  { arkit: { mouthSmileRight: 0.7, mouthDimpleRight: 0.4 }, vrm: { happy: 0.12 }, duration: [0.25, 0.6], amplitude: [0.08, 0.2], affinity: ["joy", "smug", "love", "shy"] },
  { arkit: both("noseSneer", 0.6), duration: [0.15, 0.3], amplitude: [0.08, 0.16], affinity: ["disgust", "anger", "thinking"] },
  { arkit: merge(both("eyeSquint", 0.6), both("cheekSquint", 0.4)), duration: [0.2, 0.45], amplitude: [0.08, 0.18] },
  { arkit: { mouthPressLeft: 0.4, mouthPressRight: 0.4, mouthRollLower: 0.5 }, duration: [0.2, 0.5], amplitude: [0.1, 0.2], affinity: ["shy", "thinking", "sorrow"] },
  { arkit: { browDownLeft: 0.6, browInnerUp: 0.2 }, duration: [0.2, 0.45], amplitude: [0.08, 0.18], affinity: ["thinking", "anger", "sorrow"] },
];

export interface ExpressionMixerOptions {
  rng?: () => number;
  /** Per-channel exponential rates (1/s). */
  attackRate?: number;
  decayRate?: number;
  /** Max relative L/R deviation, 0..0.5. */
  asymmetry?: number;
  /** Average micro-expressions per second. */
  microRate?: number;
  /** Rate for the emotion weights themselves (separate from per-channel easing). */
  emotionRate?: number;
}

export interface ExpressionFrame {
  emotions: Record<EmotionName, number>;
  arkit: Record<ArkitName, number>;
  vrm: Record<VrmPresetKey, number>;
  /** Flicker-only VRM deltas, for preset rigs whose base emotion is owned elsewhere. */
  microVrm: Record<VrmPresetKey, number>;
}

const PAIRS: [ArkitName, ArkitName][] = ARKIT_BLENDSHAPES
  .filter((n) => n.endsWith("Left"))
  .map((l) => [l, l.replace(/Left$/, "Right") as ArkitName]);

const VRM_KEYS: VrmPresetKey[] = ["happy", "angry", "sad", "relaxed", "surprised", "neutral"];
const zeroRecord = <K extends string>(keys: readonly K[]) =>
  Object.fromEntries(keys.map((k) => [k, 0])) as Record<K, number>;

interface ActiveMicro { def: MicroExpression; t: number; duration: number; amp: number }

export class ExpressionMixer {
  private rng: () => number;
  private attack: number;
  private decay: number;
  private asymLimit: number;
  private microRate: number;
  private emotionRate: number;
  private emotionTarget = normalizeEmotions({});
  private emotion = normalizeEmotions({});
  private asym = new Map<ArkitName, { value: number; target: number }>();
  private asymTimer = 0;
  private micro: ActiveMicro[] = [];
  private microCooldown = 0;
  private frame: ExpressionFrame;
  private eased = zeroRecord(ARKIT_BLENDSHAPES);

  constructor(opts: ExpressionMixerOptions = {}) {
    this.rng = opts.rng ?? Math.random;
    this.attack = opts.attackRate ?? 10;
    this.decay = opts.decayRate ?? 4;
    this.asymLimit = Math.max(0, Math.min(0.5, opts.asymmetry ?? 0.12));
    this.microRate = opts.microRate ?? 0.18;
    this.emotionRate = opts.emotionRate ?? 5;
    this.frame = {
      emotions: { ...this.emotion },
      arkit: zeroRecord(ARKIT_BLENDSHAPES),
      vrm: zeroRecord(VRM_KEYS),
      microVrm: zeroRecord(VRM_KEYS),
    };
    for (const [l, r] of PAIRS) {
      this.asym.set(l, { value: 0, target: 0 });
      this.asym.set(r, { value: 0, target: 0 });
    }
  }

  setEmotions(weights: EmotionWeights, cap = 1): void {
    this.emotionTarget = normalizeEmotions(weights, cap);
  }

  /** Force a micro-expression now. */
  triggerMicro(index: number): void {
    this.micro.push(this.spawn(MICRO_EXPRESSIONS[index % MICRO_EXPRESSIONS.length]));
  }

  private spawn(def: MicroExpression): ActiveMicro {
    const [d0, d1] = def.duration;
    const [a0, a1] = def.amplitude;
    return { def, t: 0, duration: d0 + this.rng() * (d1 - d0), amp: a0 + this.rng() * (a1 - a0) };
  }

  private pickMicro(): MicroExpression {
    const w = MICRO_EXPRESSIONS.map((m) =>
      m.affinity ? 0.15 + m.affinity.reduce((s, e) => s + this.emotion[e], 0) * 2 : 1);
    let r = this.rng() * w.reduce((a, b) => a + b, 0);
    for (let i = 0; i < w.length; i++) {
      r -= w[i];
      if (r <= 0) return MICRO_EXPRESSIONS[i];
    }
    return MICRO_EXPRESSIONS[0];
  }

  update(dt: number, suppressMicro = false): ExpressionFrame {
    dt = Math.max(0, Math.min(dt, 0.1));
    const f = this.frame;

    for (const name of EMOTION_NAMES) {
      const cur = this.emotion[name];
      const tgt = this.emotionTarget[name];
      const rate = tgt > cur ? this.emotionRate * 1.6 : this.emotionRate * 0.7;
      this.emotion[name] = cur + (tgt - cur) * (1 - Math.exp(-dt * rate));
      f.emotions[name] = this.emotion[name];
    }

    // Slow wandering L/R bias so the face is never perfectly symmetric.
    this.asymTimer -= dt;
    if (this.asymTimer <= 0) {
      this.asymTimer = 1.5 + this.rng() * 3;
      for (const [l, r] of PAIRS) {
        const bias = (this.rng() * 2 - 1) * this.asymLimit;
        this.asym.get(l)!.target = bias;
        this.asym.get(r)!.target = -bias;
      }
    }
    const asymAlpha = 1 - Math.exp(-dt * 1.2);
    for (const a of this.asym.values()) a.value += (a.target - a.value) * asymAlpha;

    this.microCooldown -= dt;
    if (!suppressMicro && this.microCooldown <= 0 && this.micro.length < 2) {
      this.microCooldown = 0.4 + -Math.log(1 - this.rng() * 0.999) / Math.max(0.01, this.microRate);
      this.micro.push(this.spawn(this.pickMicro()));
    }

    const target = zeroRecord(ARKIT_BLENDSHAPES);
    const vrmTarget = zeroRecord(VRM_KEYS);
    for (const name of EMOTION_NAMES) {
      const w = this.emotion[name];
      if (w < 1e-4) continue;
      const p = EMOTION_PROFILES[name];
      for (const k in p.arkit) target[k as ArkitName] += (p.arkit[k as ArkitName] ?? 0) * w;
      for (const k in p.vrm) vrmTarget[k as VrmPresetKey] += (p.vrm[k as VrmPresetKey] ?? 0) * w;
    }
    for (const [name, a] of this.asym) {
      if (target[name] > 0) target[name] *= 1 + a.value;
    }

    const aA = 1 - Math.exp(-dt * this.attack);
    const aD = 1 - Math.exp(-dt * this.decay);
    for (const n of ARKIT_BLENDSHAPES) {
      const cur = this.eased[n];
      const tgt = clamp01(target[n]);
      f.arkit[n] = this.eased[n] = cur + (tgt - cur) * (tgt > cur ? aA : aD);
    }
    for (const k of VRM_KEYS) {
      const cur = f.vrm[k];
      const tgt = clamp01(vrmTarget[k]);
      f.vrm[k] = cur + (tgt - cur) * (tgt > cur ? aA : aD);
      f.microVrm[k] = 0;
    }

    // Flickers are layered after easing so they stay crisp.
    for (let i = this.micro.length - 1; i >= 0; i--) {
      const m = this.micro[i];
      m.t += dt;
      if (m.t >= m.duration) { this.micro.splice(i, 1); continue; }
      const env = Math.sin((m.t / m.duration) * Math.PI) ** 2 * m.amp;
      for (const k in m.def.arkit) {
        const n = k as ArkitName;
        f.arkit[n] = clamp01(f.arkit[n] + (m.def.arkit[n] ?? 0) * env);
      }
      for (const k in m.def.vrm) f.microVrm[k as VrmPresetKey] += (m.def.vrm[k as VrmPresetKey] ?? 0) * env;
    }
    return f;
  }

  get activeMicroCount(): number { return this.micro.length; }
}
