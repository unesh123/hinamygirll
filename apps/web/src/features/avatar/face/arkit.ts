/** Apple ARKit 52 blendshape names (the de-facto standard for realistic faces). */
export const ARKIT_BLENDSHAPES = [
  "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
  "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
  "eyeBlinkLeft", "eyeBlinkRight",
  "eyeLookDownLeft", "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight",
  "eyeLookOutLeft", "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight",
  "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft", "eyeWideRight",
  "jawForward", "jawLeft", "jawOpen", "jawRight",
  "mouthClose", "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft", "mouthFrownRight",
  "mouthFunnel", "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight",
  "mouthPressLeft", "mouthPressRight", "mouthPucker", "mouthRight",
  "mouthRollLower", "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper",
  "mouthSmileLeft", "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight",
  "mouthUpperUpLeft", "mouthUpperUpRight",
  "noseSneerLeft", "noseSneerRight", "tongueOut",
] as const;

export type ArkitName = (typeof ARKIT_BLENDSHAPES)[number];
export type ArkitWeights = Partial<Record<ArkitName, number>>;

export const ARKIT_COUNT = ARKIT_BLENDSHAPES.length;

/** Lower-cased lookup key; a trailing capital L/R after a lowercase letter means Left/Right. */
export function arkitKey(name: string): string {
  return name
    .replace(/[\s_\-.]/g, "")
    .replace(/([a-z])L$/, "$1Left")
    .replace(/([a-z])R$/, "$1Right")
    .toLowerCase();
}

const CANONICAL = new Map<string, ArkitName>(ARKIT_BLENDSHAPES.map((n) => [arkitKey(n), n]));

/** Resolve an arbitrary morph/expression name (PerfectSync, CC4, RPM, Blender) to its ARKit name. */
export function resolveArkitName(name: string): ArkitName | null {
  return CANONICAL.get(arkitKey(name)) ?? null;
}

export const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v);

/** Mulberry32 — small seeded PRNG so face motion is reproducible in tests. */
export function seededRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
