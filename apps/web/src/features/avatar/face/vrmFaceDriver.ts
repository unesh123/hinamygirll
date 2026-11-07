import type { ArkitName } from "./arkit";
import { applyArkitToExpressions, type ExpressionManagerLike } from "./applyTargets";
import type { ModelCapability } from "./capability";
import type { FaceFrame } from "./faceEngine";
import { VOWELS, type Vowel } from "./lipSync";

/**
 * Channels the legacy VRM pipeline in AvatarPresence already owns (blink, gaze, jaw/mouth shape).
 * The face engine leaves them alone on VRM rigs so two systems never fight over one morph.
 */
export const VRM_LEGACY_OWNED: ReadonlySet<ArkitName> = new Set<ArkitName>([
  "eyeBlinkLeft", "eyeBlinkRight",
  "eyeLookUpLeft", "eyeLookUpRight", "eyeLookDownLeft", "eyeLookDownRight",
  "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight",
  "jawOpen", "jawForward", "jawLeft", "jawRight",
  "mouthClose", "mouthFunnel", "mouthPucker", "mouthSmileLeft", "mouthSmileRight",
  "mouthLowerDownLeft", "mouthLowerDownRight",
]);

export interface VrmFaceDriverDeps {
  em: ExpressionManagerLike & { getValue?: (name: string) => number | null };
  /** Writes through the rig's registered name resolution. */
  set: (name: string, value: number) => void;
  /** Preset name per vowel (e.g. aa → "aa"). */
  vowelPreset: Record<Vowel, string>;
  /** Text-timed mouth weights, blended with the audio estimate in place. */
  mouthWeights: Record<Vowel, number>;
}

/** Audio estimate wins, but keeps a little of the text timeline so consonant timing still shows. */
const AUDIO_MIX = 0.7;

export function applyVrmFaceFrame(frame: FaceFrame, capability: ModelCapability, deps: VrmFaceDriverDeps): void {
  const { em, set, vowelPreset, mouthWeights } = deps;

  if (capability.hasArkit) {
    applyArkitToExpressions(em, capability, frame.arkit, VRM_LEGACY_OWNED);
  } else {
    for (const key of Object.keys(frame.microVrm) as (keyof typeof frame.microVrm)[]) {
      const delta = frame.microVrm[key];
      if (delta < 0.002) continue;
      let base = 0;
      try { base = em.getValue?.(key) ?? 0; } catch { /* unresolved preset */ }
      set(key, Math.min(1, base + delta));
    }
  }

  if (!frame.audioLipSync) return;
  const lip = frame.lip;
  for (const v of VOWELS) {
    const mixed = mouthWeights[v] + (lip[v] - mouthWeights[v]) * AUDIO_MIX;
    mouthWeights[v] = mixed;
    set(vowelPreset[v], Math.max(0, mixed));
  }
  set("jawOpen", lip.jawOpen);
  set("mouthOpen", lip.jawOpen);
  set("mouthFunnel", lip.mouthFunnel);
  set("mouthPucker", lip.mouthPucker);
  set("mouthSmile", Math.max(0.12, lip.mouthSmile));
  set("mouthClose", lip.jawOpen < 0.05 ? lip.mouthClose : 0);
}
