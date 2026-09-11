import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import {
  SEMANTIC_RUNTIME_MAP,
  performanceSequenceSchema,
  type PerformanceCue,
  type PerformanceSequence,
  type SemanticMotion,
} from "./performanceTypes";

const GESTURE_TO_SEMANTIC: Record<string, SemanticMotion> = {
  none: "none",
  small_nod: "small_nod",
  head_shake: "apology_correction",
  gentle_head_tilt: "happy_ack",
  wave: "friendly_greeting",
  explain: "thoughtful_pause",
  celebrate: "mild_celebrate",
  reassure: "calm_reassure",
  listening_lean: "listening",
};

export interface ActivePerformanceFrame {
  generation: number;
  emotion: string;
  gesture: string;
  semantic: SemanticMotion;
  intensity: number;
  jawEnergy: number;
  blinking: boolean;
  reducedMotion: boolean;
  lipSyncLevel: "amplitude" | "viseme" | "phoneme";
}

export interface PerformanceSchedulerOptions {
  now?: () => number;
  reducedMotion?: boolean;
  /** Render tier: high/medium/low scale motion; emergency yields a static frame. */
  tier?: PerformanceTier;
  /** Injected randomness for safe parameter jitter (tests use a fixed rng). */
  rng?: () => number;
}

export type PerformanceTier = "high" | "medium" | "low" | "emergency";

const TIER_SCALE: Record<
  Exclude<PerformanceTier, "emergency">,
  { gestureDuration: number; intensity: number }
> = {
  high: { gestureDuration: 1, intensity: 1 },
  medium: { gestureDuration: 0.85, intensity: 0.9 },
  low: { gestureDuration: 0.6, intensity: 0.75 },
};

/** Major-gesture cooldown: identical semantics inside this window are de-emphasized. */
const REPETITION_COOLDOWN_MS = 2_000;
const REPETITION_HISTORY = 5;

/**
 * Client-side Phase 4 performance clock.
 * Uses monotonic performance.now(); cancels stale generations.
 */
export class PerformanceScheduler {
  private generation = 0;
  private sequence: PerformanceSequence | null = null;
  private originMs = 0;
  private jawEnergy = 0;
  private reducedMotion: boolean;
  private tier: PerformanceTier;
  private readonly now: () => number;
  private readonly rng: () => number;
  private recentSemantics: SemanticMotion[] = [];
  private lastSemanticAtMs = -Infinity;

  constructor(options: PerformanceSchedulerOptions = {}) {
    this.now = options.now ?? (() => performance.now());
    this.reducedMotion = options.reducedMotion ?? false;
    this.tier = options.tier ?? "high";
    this.rng = options.rng ?? Math.random;
  }

  get currentGeneration(): number {
    return this.generation;
  }

  setReducedMotion(value: boolean): void {
    this.reducedMotion = value;
  }

  setTier(tier: PerformanceTier): void {
    this.tier = tier;
  }

  interrupt(): number {
    this.generation += 1;
    this.sequence = null;
    this.jawEnergy = 0;
    return this.generation;
  }

  setJawEnergy(energy: number, generation: number): void {
    if (generation !== this.generation) return;
    this.jawEnergy = Math.max(0, Math.min(1, energy));
  }

  loadFromPlan(
    plan: AssistantTurnPlan,
    generation?: number,
  ): PerformanceSequence {
    const gen = generation ?? this.generation;
    if (generation !== undefined && generation !== this.generation) {
      // Stale plan — ignore.
      return performanceSequenceSchema.parse({
        generation: this.generation,
        createdAtMs: this.now(),
        lipSyncLevel: "viseme",
        cues: [],
      });
    }
    const semantic =
      GESTURE_TO_SEMANTIC[plan.performance.gesture] ?? "neutral_idle";
    const tierScale =
      this.tier === "emergency" ? { gestureDuration: 0, intensity: 0 } : TIER_SCALE[this.tier];
    const durationMs = Math.min(
      12_000,
      Math.max(1_200, plan.spokenText.length * 45),
    );

    // Emergency tier: static portrait — no procedural cues at all.
    if (this.tier === "emergency") {
      const sequence = performanceSequenceSchema.parse({
        generation: gen,
        createdAtMs: this.now(),
        lipSyncLevel: "amplitude",
        cues: [],
      });
      this.sequence = sequence;
      this.originMs = this.now();
      this.generation = gen;
      return sequence;
    }

    // Safe randomization: subtle speed, timing and intensity variation keeps
    // repeated gestures from looking mechanical. Skipped under reduced motion
    // so the calm mode stays fully deterministic.
    const speedJitter = this.reducedMotion ? 1 : 0.92 + this.rng() * 0.16;
    const startJitter = this.reducedMotion ? 0 : Math.round(this.rng() * 60);
    const intensityJitter = this.reducedMotion ? 0 : this.rng() * 0.08;

    // Repetition avoidance: a semantic repeated inside the cooldown window (or
    // within the recent history) is de-emphasized — quieter, shorter, later —
    // instead of replayed at full strength.
    const isRepeat =
      this.recentSemantics.includes(semantic) &&
      elapsedSince(this.lastSemanticAtMs, this.now()) < REPETITION_COOLDOWN_MS;
    this.recentSemantics.push(semantic);
    if (this.recentSemantics.length > REPETITION_HISTORY) this.recentSemantics.shift();
    this.lastSemanticAtMs = this.now();
    const repeatScale = isRepeat ? { duration: 0.75, intensity: 0.55 } : { duration: 1, intensity: 1 };

    const gestureDurationMs = Math.min(
      2_400,
      durationMs * 0.35 * tierScale.gestureDuration * repeatScale.duration,
    );
    const cues: PerformanceCue[] = [
      {
        id: `emotion-${gen}`,
        kind: "emotion",
        semantic,
        startMs: 0,
        durationMs,
        priority: 10,
        intensity: clamp01(plan.emotion.intensity * tierScale.intensity),
        blendInMs: 120,
        blendOutMs: 180,
        generation: gen,
        facePreset: plan.performance.facePreset,
      },
      {
        id: `gesture-${gen}`,
        kind: "gesture",
        semantic,
        startMs: 80 + startJitter,
        durationMs: gestureDurationMs * speedJitter,
        priority: 40,
        intensity: clamp01(
          Math.min(1, plan.emotion.intensity + 0.1 + intensityJitter) *
            tierScale.intensity *
            repeatScale.intensity,
        ),
        blendInMs: 100,
        blendOutMs: 220,
        generation: gen,
        gesture: plan.performance.gesture,
      },
      {
        id: `idle-${gen}`,
        kind: "idle",
        semantic: "return_neutral",
        startMs: durationMs,
        durationMs: 600,
        priority: 5,
        intensity: 0.2,
        blendInMs: 160,
        blendOutMs: 160,
        generation: gen,
      },
    ];
    if (this.reducedMotion) {
      for (const cue of cues) {
        cue.intensity = Math.min(cue.intensity, 0.25);
        if (cue.kind === "gesture")
          cue.durationMs = Math.min(cue.durationMs, 400);
      }
    }
    const sequence = performanceSequenceSchema.parse({
      generation: gen,
      createdAtMs: this.now(),
      lipSyncLevel: "viseme",
      cues,
    });
    this.sequence = sequence;
    this.originMs = this.now();
    this.generation = gen;
    return sequence;
  }

  private activeCues(elapsedMs: number): PerformanceCue[] {
    if (!this.sequence) return [];
    return this.sequence.cues
      .filter(
        (cue) =>
          cue.generation === this.generation &&
          elapsedMs >= cue.startMs &&
          elapsedMs < cue.startMs + cue.durationMs,
      )
      .sort((a, b) => b.priority - a.priority);
  }

  sample(generation = this.generation): ActivePerformanceFrame {
    if (generation !== this.generation || !this.sequence) {
      return {
        generation: this.generation,
        emotion: "neutral",
        gesture: "none",
        semantic: "neutral_idle",
        intensity: 0,
        jawEnergy: 0,
        blinking: false,
        reducedMotion: this.reducedMotion,
        lipSyncLevel: "amplitude",
      };
    }
    const elapsed = this.now() - this.originMs;
    const active = this.activeCues(elapsed);
    const top = active[0];
    const semantic = top?.semantic ?? "neutral_idle";
    const mapped = SEMANTIC_RUNTIME_MAP[semantic];
    const emotionCue = active.find((cue) => cue.kind === "emotion");
    return {
      generation: this.generation,
      emotion: emotionCue?.facePreset ?? mapped.cssEmotion ?? "neutral",
      gesture: top?.gesture ?? mapped.cssGesture,
      semantic,
      intensity: top?.intensity ?? 0,
      jawEnergy: this.reducedMotion ? 0 : this.jawEnergy,
      blinking: !this.reducedMotion && Math.floor(elapsed / 3200) % 2 === 0,
      reducedMotion: this.reducedMotion,
      lipSyncLevel: this.sequence.lipSyncLevel,
    };
  }
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function elapsedSince(earlierMs: number, nowMs: number): number {
  return nowMs - earlierMs;
}
