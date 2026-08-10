/**
 * vrmExpressionMap — pure mapping from the avatar performance frame to
 * VRM 1.0 expression weights.
 *
 * HINAA's emotion vocabulary (happy, excited, playful, shy, concerned, sad,
 * surprised, thinking, neutral) is translated to VRM preset expressions
 * (happy, sad, surprised, relaxed, neutral), with viseme presets (aa, ih, ou)
 * driven by jaw energy for lip-sync, and blink presets for blinking.
 *
 * Kept framework-free so it can be unit-tested and reused by any renderer.
 */

export interface VrmExpressionWeights {
  happy: number;
  angry: number;
  sad: number;
  relaxed: number;
  surprised: number;
  neutral: number;
  blink: number;
  blinkLeft: number;
  blinkRight: number;
  aa: number;
  ih: number;
  ou: number;
  ee: number;
  oh: number;
}

export interface VrmExpressionInput {
  /** Companion emotion from the performance frame or plan. */
  emotion: string;
  /** Face preset from the plan (soft_smile, big_smile, blush, …). */
  facePreset?: string;
  /** Plan emotion intensity, 0..1. */
  intensity: number;
  /** Audio RMS jaw energy, 0..1 (drives lip sync while speaking). */
  jawEnergy: number;
  /** True while the scheduler says the avatar should blink. */
  blinking: boolean;
  /** True while the companion is in the speaking state. */
  speaking: boolean;
  /** Reduced-motion: calm expressions, no blink animation. */
  reducedMotion: boolean;
}

export const VRM_EXPRESSION_KEYS: (keyof VrmExpressionWeights)[] = [
  "happy",
  "angry",
  "sad",
  "relaxed",
  "surprised",
  "neutral",
  "blink",
  "blinkLeft",
  "blinkRight",
  "aa",
  "ih",
  "ou",
  "ee",
  "oh",
];

/** Emotion → base VRM preset weights (scaled by plan intensity). */
const EMOTION_TARGETS: Record<string, Partial<VrmExpressionWeights>> = {
  happy: { happy: 0.55, relaxed: 0.18 },
  excited: { happy: 0.8, aa: 0.35, relaxed: 0.1 },
  playful: { happy: 0.5, ih: 0.28, relaxed: 0.15 },
  shy: { happy: 0.28, relaxed: 0.32 },
  concerned: { sad: 0.35, aa: 0.12, relaxed: 0.15 },
  sad: { sad: 0.75, relaxed: 0.1 },
  surprised: { surprised: 0.85, aa: 0.4 },
  thinking: { neutral: 0.4, aa: 0.12 },
  neutral: { relaxed: 0.22, neutral: 0.12 },
};

/** Face preset → extra/overriding expression weights. */
const FACE_PRESET_TARGETS: Record<string, Partial<VrmExpressionWeights>> = {
  soft_smile: { happy: 0.5, relaxed: 0.15 },
  big_smile: { happy: 1.0 },
  blush: { happy: 0.35, relaxed: 0.3 },
  pout: { ou: 0.4 },
  concerned: { sad: 0.3, aa: 0.1 },
  surprised: { surprised: 0.7, aa: 0.3 },
  thinking: { aa: 0.1, neutral: 0.3 },
};

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function buildVrmExpressionWeights(
  input: VrmExpressionInput,
): VrmExpressionWeights {
  const weights: VrmExpressionWeights = {
    happy: 0,
    angry: 0,
    sad: 0,
    relaxed: 0.15,
    surprised: 0,
    neutral: 0,
    blink: 0,
    blinkLeft: 0,
    blinkRight: 0,
    aa: 0,
    ih: 0,
    ou: 0,
    ee: 0,
    oh: 0,
  };

  const emotionScale = clamp01(input.intensity);
  const emotionTarget = EMOTION_TARGETS[input.emotion];
  if (emotionTarget) {
    for (const [key, value] of Object.entries(emotionTarget)) {
      const name = key as keyof VrmExpressionWeights;
      weights[name] = Math.max(weights[name], value * emotionScale);
    }
  }

  const preset = input.facePreset;
  if (preset && FACE_PRESET_TARGETS[preset]) {
    for (const [key, value] of Object.entries(FACE_PRESET_TARGETS[preset])) {
      const name = key as keyof VrmExpressionWeights;
      weights[name] = Math.max(weights[name], value);
    }
  }

  // Lip sync — jaw energy drives the open/rounded visemes while speaking.
  if (input.speaking) {
    const jaw = clamp01(input.jawEnergy);
    weights.aa = Math.max(weights.aa, jaw * 0.9);
    weights.ih = Math.max(weights.ih, jaw * 0.3);
    weights.ou = Math.max(weights.ou, jaw * 0.2);
    weights.oh = Math.max(weights.oh, jaw * 0.15);
  }

  // Blink — full closure on blink beats, none otherwise (VRM 1.0).
  const blink = input.reducedMotion ? 0 : input.blinking ? 1 : 0;
  weights.blink = blink;
  weights.blinkLeft = blink;
  weights.blinkRight = blink;

  // Reduced motion: calm the whole face down.
  if (input.reducedMotion) {
    for (const key of VRM_EXPRESSION_KEYS) {
      if (key === "blink" || key === "blinkLeft" || key === "blinkRight") continue;
      weights[key] *= 0.4;
    }
  }

  for (const key of VRM_EXPRESSION_KEYS) {
    weights[key] = Math.round(clamp01(weights[key]) * 1000) / 1000;
  }
  return weights;
}
