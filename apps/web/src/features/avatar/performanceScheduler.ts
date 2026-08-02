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
}

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
  private readonly now: () => number;

  constructor(options: PerformanceSchedulerOptions = {}) {
    this.now = options.now ?? (() => performance.now());
    this.reducedMotion = options.reducedMotion ?? false;
  }

  get currentGeneration(): number {
    return this.generation;
  }

  setReducedMotion(value: boolean): void {
    this.reducedMotion = value;
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
        lipSyncLevel: "amplitude",
        cues: [],
      });
    }
    const semantic =
      GESTURE_TO_SEMANTIC[plan.performance.gesture] ?? "neutral_idle";
    const durationMs = Math.min(
      12_000,
      Math.max(1_200, plan.spokenText.length * 45),
    );
    const cues: PerformanceCue[] = [
      {
        id: `emotion-${gen}`,
        kind: "emotion",
        semantic,
        startMs: 0,
        durationMs,
        priority: 10,
        intensity: plan.emotion.intensity,
        blendInMs: 120,
        blendOutMs: 180,
        generation: gen,
        facePreset: plan.performance.facePreset,
      },
      {
        id: `gesture-${gen}`,
        kind: "gesture",
        semantic,
        startMs: 80,
        durationMs: Math.min(2_400, durationMs * 0.35),
        priority: 40,
        intensity: Math.min(1, plan.emotion.intensity + 0.1),
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
      lipSyncLevel: "amplitude",
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
