/**
 * textToViseme.ts — Text-to-Viseme mapper
 * 
 * Converts spoken text into a timed sequence of VRM mouth expression events.
 * These events are consumed by AvatarPresence each animation frame using the
 * AudioContext playback clock as timing authority.
 * 
 * Viseme mapping for VRM expressions:
 *   aa → open vowels: A, AH, AW
 *   ih → front vowels: E, EH, IH
 *   ou → back/rounded: O, OW, UH, UW
 *   ee → high front: IY, EY  
 *   oh → mid-back: OY, AO
 */

export type VrmMouth = "aa" | "ih" | "ou" | "ee" | "oh" | "closed";

export interface VisemeEvent {
  timeMs: number;       // when this viseme starts (relative to audio start)
  durationMs: number;   // how long it lasts
  mouth: VrmMouth;
  weight: number;       // 0-1 intensity
}

// ── Phoneme → viseme classification ──────────────────────────────────────────
// ARPAbet-inspired groups mapped to VRM mouth expressions
const PHONEME_MAP: Record<string, VrmMouth> = {
  // Open vowels → AA
  a: "aa", A: "aa", ah: "aa", AH: "aa", aw: "aa", AW: "aa",
  // Front closed vowels → IH
  e: "ih", E: "ih", eh: "ih", EH: "ih", ih: "ih", IH: "ih",
  // Back/rounded vowels → OU  
  o: "ou", O: "ou", ow: "ou", OW: "ou", uh: "ou", UH: "ou", uw: "ou", UW: "ou",
  u: "ou", U: "ou",
  // High front vowels → EE
  i: "ee", I: "ee", iy: "ee", IY: "ee", ey: "ee", EY: "ee",
  // Mid-back vowels → OH
  ao: "oh", AO: "oh", oy: "oh", OY: "oh",
  // Consonants (minimal opening)
  p: "closed", b: "closed", m: "closed",
  f: "ih", v: "ih",
  th: "ih", dh: "ih",
  s: "ih", z: "ih",
  sh: "ou", zh: "ou", ch: "ou", jh: "ou",
  t: "ih", d: "ih", n: "ih", l: "ih",
  r: "ou",
  k: "aa", g: "aa", ng: "aa",
  h: "aa",
  w: "ou",
  y: "ee",
};

// Letter-based fallback classification  
const CHAR_VOWEL_MAP: Record<string, VrmMouth> = {
  a: "aa", e: "ih", i: "ee", o: "ou", u: "ou",
  A: "aa", E: "ih", I: "ee", O: "ou", U: "ou",
};

/**
 * Classify a single character into a VRM mouth shape
 */
function charToMouth(char: string): VrmMouth {
  const lower = char.toLowerCase();
  // Vowels
  if ("aeiou".includes(lower)) {
    return CHAR_VOWEL_MAP[lower] ?? "aa";
  }
  // Bilabial consonants → near-closed
  if ("bpm".includes(lower)) return "closed";
  // Default for consonants — slight opening
  return "ih";
}

/**
 * Convert plain text + estimated total duration into a stream of VisemeEvents.
 *
 * Since we don't have phoneme-level timing, we distribute events uniformly
 * weighted by character count, skipping whitespace and punctuation.
 *
 * @param text        The text being spoken
 * @param durationMs  Total audio duration in ms
 * @param startMs     Audio start offset (default 0)
 */
export function textToVisemeEvents(
  text: string,
  durationMs: number,
  startMs = 0,
): VisemeEvent[] {
  if (!text || durationMs <= 0) return [];

  // Filter to speakable characters only
  const chars = Array.from(text).filter(c => /[a-zA-Z]/i.test(c));
  if (chars.length === 0) return [];

  const events: VisemeEvent[] = [];
  const perChar = durationMs / chars.length;

  let charIdx = 0;
  for (const char of chars) {
    const mouth = charToMouth(char);
    const timeMs = startMs + charIdx * perChar;

    // Merge consecutive same-mouth events
    const last = events[events.length - 1];
    if (last && last.mouth === mouth) {
      last.durationMs += perChar;
    } else {
      events.push({
        timeMs,
        durationMs: perChar,
        mouth,
        weight: mouth === "closed" ? 0.05 : (mouth === "aa" ? 1.0 : 0.75),
      });
    }
    charIdx++;
  }

  return events;
}

/**
 * Given a current playback time (ms from audio start) and a list of viseme events,
 * returns the active viseme or null if between events (silence).
 */
export function getActiveViseme(
  playTimeMs: number,
  events: VisemeEvent[],
): VisemeEvent | null {
  // Binary search for the current event
  let lo = 0, hi = events.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const ev = events[mid];
    if (playTimeMs < ev.timeMs) {
      hi = mid - 1;
    } else if (playTimeMs >= ev.timeMs + ev.durationMs) {
      lo = mid + 1;
    } else {
      return ev;
    }
  }
  // Check if we're in a gap — return the next event with low weight for coarticulation
  if (lo < events.length && events[lo].timeMs - playTimeMs < 80) {
    return { ...events[lo], weight: 0.3 };
  }
  return null;
}
