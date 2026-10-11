import type { VisemeEvent, VrmMouth } from "../audio/textToViseme";

export type MouthTargetKey = Exclude<VrmMouth, "closed">;

export interface CoarticulatedMouthTarget {
  /** Primary mouth shape for the currently sounding viseme. */
  mouth: MouthTargetKey | null;
  weight: number;
  /** Anticipated next shape, blended in early so the mouth pre-forms it. */
  lookaheadMouth: MouthTargetKey | null;
  lookaheadWeight: number;
}

const TO_MOUTH: Record<string, MouthTargetKey> = {
  aa: "aa", ih: "ih", ou: "ou", ee: "ee", oh: "oh",
};

/** Weight of the anticipatory blend — real coarticulation shapes the next
 *  phoneme well before it sounds; 35% reads as fluid without smearing. */
export const COARTICULATION_FACTOR = 0.35;
/** How far ahead of the audio clock the upcoming viseme is sampled (ms). */
export const COARTICULATION_LOOKAHEAD_MS = 50;

/**
 * Computes the mouth targets for one frame of lip-sync. A real mouth never
 * holds exactly one shape per phoneme: it attacks the current viseme while
 * already drifting toward the next one. Returning both targets lets the
 * easing loop keep two shapes alive at once instead of snapping between them.
 */
export function computeCoarticulatedMouthTarget(
  active: VisemeEvent | null,
  upcoming: VisemeEvent | null,
  energy: number,
): CoarticulatedMouthTarget {
  let mouth: MouthTargetKey | null = null;
  let weight = 0;
  if (active && active.mouth !== "closed") {
    mouth = TO_MOUTH[active.mouth] ?? "aa";
    weight = Math.max(0.10, active.weight * energy);
  }
  let lookaheadMouth: MouthTargetKey | null = null;
  let lookaheadWeight = 0;
  if (upcoming && upcoming.mouth !== "closed") {
    const la = TO_MOUTH[upcoming.mouth] ?? "aa";
    if (la !== mouth) {
      lookaheadMouth = la;
      lookaheadWeight = Math.max(0.08, upcoming.weight * energy * COARTICULATION_FACTOR);
    }
  }
  return { mouth, weight, lookaheadMouth, lookaheadWeight };
}
