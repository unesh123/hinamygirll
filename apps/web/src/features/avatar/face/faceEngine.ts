import { ARKIT_BLENDSHAPES, clamp01, type ArkitName } from "./arkit";
import { BodyMotion, type BodyPose } from "./bodyMotion";
import type { ModelCapability } from "./capability";
import { eyeContextFor, EyeSystem, type EyeFrame } from "./eyeSystem";
import {
  ExpressionMixer, type EmotionName, type EmotionWeights, type VrmPresetKey,
} from "./expressionMixer";
import { AudioLipSync, type LipSyncFrame } from "./lipSync";

/** Structural subset of AffectiveProfile so this module stays free of app imports. */
export interface AffectInput {
  valence: number;
  arousal: number;
  playfulness: number;
  warmth: number;
  surprise: number;
  thoughtfulness: number;
  pout: number;
  confidence: number;
  drowsy: number;
  scenarioArchetype?: string;
}

export function emotionsFromAffect(a: AffectInput): EmotionWeights {
  const pos = Math.max(0, a.valence);
  const neg = Math.max(0, -a.valence);
  const shy = a.scenarioArchetype === "shy_flustered" ? 0.65 : 0;
  const distress = neg > 0.35 && a.arousal > 0.65;
  return {
    joy: clamp01(pos * (0.55 + 0.45 * a.arousal) * (1 - shy * 0.5)),
    sorrow: clamp01(neg * (1 - a.arousal * 0.6)),
    anger: clamp01(a.pout * 0.55 + (a.scenarioArchetype === "determined_focus" ? 0.15 : 0)),
    surprise: clamp01(a.surprise * 0.9),
    fear: distress ? clamp01(neg * a.arousal * 0.6) : 0,
    disgust: 0,
    shy,
    smug: clamp01(a.playfulness * a.confidence * 0.9),
    thinking: clamp01(a.thoughtfulness * 0.9),
    sleepy: clamp01(a.drowsy),
    love: clamp01(a.warmth * pos * 0.8),
  };
}

export interface FaceEngineOptions {
  capability: ModelCapability;
  rng?: () => number;
  reducedMotion?: boolean;
}

export interface FaceInput {
  /** Emotion target; omit to keep the previous one. */
  emotions?: EmotionWeights;
  speaking: boolean;
  listening?: boolean;
  thinking?: boolean;
  /** Smoothed speech loudness 0..1 for body emphasis. */
  speechEnergy?: number;
  /** Live TTS tap; when null the caller keeps text-timed visemes. */
  analyser?: AnalyserNode | null;
}

export interface FaceFrame {
  /** ARKit weights with emotion, eyes and lip-sync merged. */
  arkit: Record<ArkitName, number>;
  vrm: Record<VrmPresetKey, number>;
  microVrm: Record<VrmPresetKey, number>;
  lip: LipSyncFrame;
  /** True when `lip` came from real audio, so it should override text-timed visemes. */
  audioLipSync: boolean;
  eye: EyeFrame;
  body: BodyPose;
}

export class FaceEngine {
  readonly capability: ModelCapability;
  private mixer: ExpressionMixer;
  private eyes: EyeSystem;
  private lips = new AudioLipSync();
  private bodyMotion: BodyMotion;
  private reducedMotion: boolean;
  private emotions: EmotionWeights = {};
  private out: FaceFrame;

  constructor({ capability, rng, reducedMotion = false }: FaceEngineOptions) {
    this.capability = capability;
    this.reducedMotion = reducedMotion;
    this.mixer = new ExpressionMixer({ rng, microRate: reducedMotion ? 0 : 0.18 });
    this.eyes = new EyeSystem(rng);
    this.bodyMotion = new BodyMotion(rng);
    const frame0 = this.mixer.update(0);
    this.out = {
      arkit: { ...frame0.arkit },
      vrm: frame0.vrm,
      microVrm: frame0.microVrm,
      lip: this.lips.step(null, 48000, 0),
      audioLipSync: false,
      eye: this.eyes.update(0),
      body: this.bodyMotion.update(0, { speaking: false, energy: 0 }),
    };
  }

  triggerNod(amplitude?: number): void { this.bodyMotion.triggerNod(amplitude); }

  update(dt: number, input: FaceInput): FaceFrame {
    if (input.emotions) {
      this.emotions = input.emotions;
      this.mixer.setEmotions(input.emotions);
    }
    const mix = this.mixer.update(dt, this.reducedMotion);
    const eyeCtx = eyeContextFor(mix.emotions, {
      thinking: input.thinking, speaking: input.speaking, listening: input.listening,
    });
    if (this.reducedMotion) eyeCtx.saccadeScale *= 0.35;
    const eye = this.eyes.update(dt, eyeCtx);

    const hasAudio = input.speaking && !!input.analyser;
    const lip = this.lips.sample(hasAudio ? input.analyser! : null, dt);
    const audioLipSync = hasAudio && lip.active;

    const o = this.out;
    for (const n of ARKIT_BLENDSHAPES) {
      const m = mix.arkit[n];
      const e = eye.arkit[n];
      o.arkit[n] = e === undefined ? m
        : n.startsWith("eyeBlink") ? 1 - (1 - m) * (1 - e)
        : clamp01(m + e);
    }
    if (audioLipSync) {
      const a = o.arkit;
      a.jawOpen = clamp01(a.jawOpen + lip.jawOpen);
      a.mouthFunnel = clamp01(a.mouthFunnel + lip.mouthFunnel);
      a.mouthPucker = clamp01(a.mouthPucker + lip.mouthPucker);
      a.mouthSmileLeft = clamp01(a.mouthSmileLeft + lip.mouthSmile);
      a.mouthSmileRight = clamp01(a.mouthSmileRight + lip.mouthSmile);
      a.mouthLowerDownLeft = clamp01(a.mouthLowerDownLeft + lip.jawOpen * 0.35);
      a.mouthLowerDownRight = clamp01(a.mouthLowerDownRight + lip.jawOpen * 0.35);
      a.mouthClose = lip.mouthClose;
    } else if (!input.speaking) {
      o.arkit.mouthClose = Math.max(o.arkit.mouthClose, lip.mouthClose * 0.5);
    }
    o.vrm = mix.vrm;
    o.microVrm = mix.microVrm;
    o.lip = lip;
    o.audioLipSync = audioLipSync;
    o.eye = eye;
    o.body = this.bodyMotion.update(dt, {
      speaking: input.speaking,
      energy: input.speechEnergy ?? lip.level,
      arousal: 1 - mix.emotions.neutral * 0.6 - mix.emotions.sleepy * 0.3,
      reducedMotion: this.reducedMotion,
    });
    return o;
  }

  get dominantEmotion(): EmotionName {
    let best: EmotionName = "neutral";
    let w = -1;
    for (const k of Object.keys(this.emotions) as EmotionName[]) {
      if ((this.emotions[k] ?? 0) > w) { w = this.emotions[k] ?? 0; best = k; }
    }
    return best;
  }
}
