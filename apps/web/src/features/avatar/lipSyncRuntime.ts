import type { VisemeEvent, VrmMouth } from "../audio/textToViseme";
import type { SpeechTimingSource } from "../audio/speechTimingSource";

export interface LipSyncBlendshapeWeights {
  aa: number;
  ih: number;
  ou: number;
  ee: number;
  oh: number;
  jawOpen: number;
  mouthSmile: number;
  mouthFunnel: number;
  mouthPucker: number;
  [key: string]: number;
}

export interface LipSyncRuntimeOptions {
  lookaheadMs?: number;      // Lookahead window in ms (default: 50ms, bounds 30-80ms)
  attackTimeMs?: number;     // Attack time in ms (default: 50ms, bounds 30-70ms)
  releaseTimeMs?: number;    // Release time in ms (default: 80ms, bounds 50-100ms)
  jawMultiplier?: number;    // Scale factor for jawOpen (default: 0.85)
}

const DEFAULT_WEIGHTS: LipSyncBlendshapeWeights = {
  aa: 0,
  ih: 0,
  ou: 0,
  ee: 0,
  oh: 0,
  jawOpen: 0,
  mouthSmile: 0,
  mouthFunnel: 0,
  mouthPucker: 0,
};

const VRM_VOWELS: readonly (keyof Pick<LipSyncBlendshapeWeights, "aa" | "ih" | "ou" | "ee" | "oh">)[] = [
  "aa",
  "ih",
  "ou",
  "ee",
  "oh",
];

export class LipSyncRuntime {
  private lookaheadMs: number;
  private attackTimeMs: number;
  private releaseTimeMs: number;
  private jawMultiplier: number;

  private currentWeights: LipSyncBlendshapeWeights = { ...DEFAULT_WEIGHTS };
  private targetWeights: LipSyncBlendshapeWeights = { ...DEFAULT_WEIGHTS };

  constructor(options: LipSyncRuntimeOptions = {}) {
    this.lookaheadMs = Math.max(30, Math.min(options.lookaheadMs ?? 50, 80));
    this.attackTimeMs = Math.max(30, Math.min(options.attackTimeMs ?? 50, 70));
    this.releaseTimeMs = Math.max(50, Math.min(options.releaseTimeMs ?? 80, 100));
    this.jawMultiplier = options.jawMultiplier ?? 0.85;
  }

  reset(): void {
    this.currentWeights = { ...DEFAULT_WEIGHTS };
    this.targetWeights = { ...DEFAULT_WEIGHTS };
  }

  getCurrentWeights(): Readonly<LipSyncBlendshapeWeights> {
    return this.currentWeights;
  }

  /**
   * Evaluates targets based on timing source or fallback events,
   * factoring in lookahead and coarticulation.
   */
  private computeTargets(
    timeMs: number,
    timingSource: SpeechTimingSource | null,
    fallbackEvents: VisemeEvent[] | null | undefined,
    isSpeaking: boolean,
    jawEnergy = 0
  ): LipSyncBlendshapeWeights {
    const targets: LipSyncBlendshapeWeights = { ...DEFAULT_WEIGHTS };

    if (!isSpeaking) {
      return targets; // Silence/rest state: all 0
    }

    // 1. Current viseme
    const currentViseme = timingSource
      ? timingSource.getVisemeAt(timeMs)
      : (fallbackEvents ? getEventAt(fallbackEvents, timeMs) : null);

    // 2. Lookahead viseme for anticipatory coarticulation
    const lookaheadViseme = timingSource
      ? timingSource.getVisemeAt(timeMs + this.lookaheadMs)
      : (fallbackEvents ? getEventAt(fallbackEvents, timeMs + this.lookaheadMs) : null);

    // Apply primary viseme
    if (currentViseme && currentViseme.mouth !== "closed") {
      const mouth = currentViseme.mouth as keyof LipSyncBlendshapeWeights;
      if (mouth in targets) {
        targets[mouth] = Math.max(0, Math.min(currentViseme.weight, 1));
      }
    }

    // Blend in upcoming viseme (lookahead coarticulation)
    if (lookaheadViseme && lookaheadViseme.mouth !== "closed") {
      const nextMouth = lookaheadViseme.mouth as keyof LipSyncBlendshapeWeights;
      if (nextMouth in targets) {
        const coarticulationFactor = 0.35; // 35% anticipation
        const lookaheadWeight = lookaheadViseme.weight * coarticulationFactor;
        targets[nextMouth] = Math.max(targets[nextMouth], lookaheadWeight);
      }
    }

    // Auxiliary blendshapes derived from vowels
    // "aa": open mouth -> high jawOpen
    // "ou": rounded mouth -> high mouthPucker / mouthFunnel
    // "ee": wide smile -> mouthSmile
    // "oh": round & open -> mouthFunnel + jawOpen
    const vowelOpen = targets.aa * 0.9 + targets.oh * 0.7 + targets.ih * 0.4 + targets.ou * 0.3;
    const effectiveJaw = Math.max(vowelOpen, jawEnergy);
    targets.jawOpen = Math.min(1, effectiveJaw * this.jawMultiplier);
    targets.mouthSmile = Math.min(1, targets.ee * 0.65 + targets.ih * 0.25);
    targets.mouthFunnel = Math.min(1, targets.oh * 0.7 + targets.ou * 0.4);
    targets.mouthPucker = Math.min(1, targets.ou * 0.85);

    return targets;
  }

  /**
   * Tick update for each frame loop (e.g. R3F useFrame).
   * Applies asymmetric attack/release smoothing (faster attack, slower natural release).
   */
  update(
    deltaSeconds: number,
    timingSource: SpeechTimingSource | null,
    options: {
      fallbackVisemes?: VisemeEvent[];
      jawEnergy?: number;
      speaking?: boolean;
      customTimeMs?: number;
    } = {}
  ): LipSyncBlendshapeWeights {
    const dt = Math.max(0.001, Math.min(deltaSeconds, 0.1)); // Guard against huge frame jumps
    const dtMs = dt * 1000;

    const isSpeaking = options.speaking ?? (timingSource ? timingSource.isPlaying() : false);
    const timeMs = options.customTimeMs ?? (timingSource ? timingSource.getPlaybackTime() : 0);
    const jawEnergy = options.jawEnergy ?? 0;

    this.targetWeights = this.computeTargets(
      timeMs,
      timingSource,
      options.fallbackVisemes,
      isSpeaking,
      jawEnergy
    );

    const attackAlpha = 1 - Math.exp(-dtMs / this.attackTimeMs);
    const releaseAlpha = 1 - Math.exp(-dtMs / this.releaseTimeMs);

    const keys = Object.keys(DEFAULT_WEIGHTS) as (keyof LipSyncBlendshapeWeights)[];
    for (const key of keys) {
      const target = this.targetWeights[key] ?? 0;
      const current = this.currentWeights[key] ?? 0;
      const alpha = target > current ? attackAlpha : releaseAlpha;
      const next = current + (target - current) * alpha;
      // Snap to 0 if very close to prevent subnormal floats
      this.currentWeights[key] = next < 0.0005 ? 0 : Math.min(1, next);
    }

    return { ...this.currentWeights };
  }
}

function getEventAt(events: readonly VisemeEvent[], timeMs: number): VisemeEvent | null {
  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (timeMs >= e.timeMs && timeMs < e.timeMs + e.durationMs) {
      return e;
    }
  }
  return null;
}
