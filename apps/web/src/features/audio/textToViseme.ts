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

// ── Devanagari (Nepali/Hindi) classification ─────────────────────────────────
// A consonant letter carries an inherent "a" (schwa), so it opens the mouth.
// A following matra (vowel sign) overrides that syllable's mouth shape.
// The virama (्) kills the inherent vowel → mouth closes.
// Independent vowels and anusvara/visarga/chandrabindu are handled explicitly.
const DEVANAGARI_INDEPENDENT_VOWELS: Record<string, VrmMouth> = {
  "\u0905": "aa", // अ a
  "\u0906": "aa", // आ aa
  "\u0907": "ee", // इ i
  "\u0908": "ee", // ई ii
  "\u0909": "ou", // उ u
  "\u090A": "ou", // ऊ uu
  "\u090B": "ee", // ऋ ri
  "\u090F": "ih", // ए e
  "\u0910": "ih", // ऐ ai
  "\u0913": "ou", // ओ o
  "\u0914": "ou", // औ au
};

// Matras: override the mouth of the syllable they attach to.
const DEVANAGARI_MATRAS: Record<string, VrmMouth> = {
  "\u093E": "aa", // ा aa
  "\u093F": "ee", // ि i
  "\u0940": "ee", // ी ii
  "\u0941": "ou", // ु u
  "\u0942": "ou", // ू uu
  "\u0943": "ee", // ृ ri
  "\u0947": "ih", // े e
  "\u0948": "ih", // ै ai
  "\u094B": "ou", // ो o
  "\u094C": "ou", // ौ au
};

const DEVANAGARI_VIRAMA = "\u094D"; // ् — inherent-vowel killer → closed
const DEVANAGARI_NASALS = new Set(["\u0902", "\u0903", "\u0941\u0902", "\u0901"]); // ं ः ँ

function isDevanagariConsonant(char: string): boolean {
  const code = char.codePointAt(0) ?? 0;
  // Consonant block क..ह (U+0915..U+0939) plus Nukta-ta variants U+0958..U+095F
  return (code >= 0x0915 && code <= 0x0939) || (code >= 0x0958 && code <= 0x095f);
}

function isSpeakable(char: string): boolean {
  return /[a-zA-Z]/i.test(char) || /[\u0900-\u097F]/.test(char);
}

/**
 * Classify a single character into a VRM mouth shape.
 * Returns null for characters that do not open the mouth on their own
 * (Devanagari matras/nasal marks — the caller applies them to the prior event).
 */
function charToMouth(char: string): VrmMouth | null {
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

  // Filter to speakable characters only (Latin + Devanagari)
  const chars = Array.from(text).filter(isSpeakable);
  if (chars.length === 0) return [];

  const events: VisemeEvent[] = [];
  const perChar = durationMs / chars.length;

  // Emit one event per speakable character. Devanagari matras and nasal marks
  // retroactively reshape the syllable they follow instead of adding their own.
  let charIdx = 0;
  for (const char of chars) {
    const timeMs = startMs + charIdx * perChar;
    const last = events[events.length - 1];

    if (isDevanagariConsonant(char)) {
      // Consonant carries an inherent "a" (schwa) → open mouth
      pushOrMerge(events, { timeMs, durationMs: perChar, mouth: "aa", weight: 0.9 });
    } else if (char === DEVANAGARI_VIRAMA) {
      // Virama kills the inherent vowel → mouth closes
      pushOrMerge(events, { timeMs, durationMs: perChar, mouth: "closed", weight: 0.05 });
    } else if (DEVANAGARI_MATRAS[char]) {
      // Matra reshapes the syllable it attaches to and its time slot belongs
      // to that syllable's vowel, so the event extends through both slots.
      if (last) {
        last.mouth = DEVANAGARI_MATRAS[char];
        last.durationMs += perChar;
      }
    } else if (DEVANAGARI_INDEPENDENT_VOWELS[char]) {
      pushOrMerge(events, {
        timeMs,
        durationMs: perChar,
        mouth: DEVANAGARI_INDEPENDENT_VOWELS[char],
        weight: 1.0,
      });
    } else if (DEVANAGARI_NASALS.has(char)) {
      // Nasal marks color the previous syllable; no separate opening
      if (last && last.weight < 1) last.weight = Math.min(1, last.weight + 0.1);
    } else {
      const mouth = charToMouth(char);
      if (mouth) {
        pushOrMerge(events, {
          timeMs,
          durationMs: perChar,
          mouth,
          weight: mouth === "closed" ? 0.05 : mouth === "aa" ? 1.0 : 0.75,
        });
      }
    }
    charIdx++;
  }

  return events;
}

function pushOrMerge(events: VisemeEvent[], event: VisemeEvent): void {
  const last = events[events.length - 1];
  if (last && last.mouth === event.mouth) {
    last.durationMs += event.durationMs;
    return;
  }
  events.push(event);
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
