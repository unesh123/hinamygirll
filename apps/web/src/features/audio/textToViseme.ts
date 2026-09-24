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

export interface LipSyncTimelineInput {
  text?: string;
  durationMs: number;
  startMs?: number;
  providerEvents?: VisemeEvent[] | null;
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

// ── Speaking time ────────────────────────────────────────────────────────────
// Relative time each character occupies in speech, normalised to the audio
// length. These are not pretty numbers — they are the reason the mouth lines up
// with the voice: a vowel is held, a stop consonant is almost instantaneous,
// and the silence inside a sentence is longer than most of the letters.
const UNIT_INDEPENDENT_VOWEL = 1.2; // अ आ इ ई उ ऊ ए ऐ ओ औ
const UNIT_DEVANAGARI_CONSONANT = 1.0; // carries a short inherent "a"
const UNIT_VOWEL = 1.1; // a e i o u
const UNIT_CONSONANT = 0.55; // other Latin letters
const UNIT_DIACRITIC = 0.35; // matra / virama / nasal mark: belongs to its syllable
const UNIT_SPACE = 0.45; // word boundary — relax, do not close
const UNIT_CLAUSE_PAUSE = 1.4; // , ; : —
const UNIT_SENTENCE_PAUSE = 2.4; // . ! ? and line breaks

const CLAUSE_PUNCTUATION = new Set([",", ";", ":", "—", "–"]);
const SENTENCE_PUNCTUATION = new Set([".", "!", "?", "\n"]);

function isPauseChar(char: string): boolean {
  return CLAUSE_PUNCTUATION.has(char) || SENTENCE_PUNCTUATION.has(char);
}

/** Speaking-time weight for one character; 0 means it occupies no time. */
function speakingTime(char: string): number {
  if (isDevanagariConsonant(char)) return UNIT_DEVANAGARI_CONSONANT;
  if (DEVANAGARI_INDEPENDENT_VOWELS[char]) return UNIT_INDEPENDENT_VOWEL;
  if (DEVANAGARI_MATRAS[char] || char === DEVANAGARI_VIRAMA || DEVANAGARI_NASALS.has(char)) {
    return UNIT_DIACRITIC;
  }
  if ("aeiouAEIOU".includes(char)) return UNIT_VOWEL;
  if (/[a-zA-Z]/.test(char)) return UNIT_CONSONANT;
  if (char === " " || char === "\t") return UNIT_SPACE;
  if (CLAUSE_PUNCTUATION.has(char)) return UNIT_CLAUSE_PAUSE;
  if (SENTENCE_PUNCTUATION.has(char)) return UNIT_SENTENCE_PAUSE;
  return 0;
}

/**
 * Convert plain text + measured audio duration into a stream of VisemeEvents.
 *
 * This is the only lip-sync timeline HINAA ever has — no voice provider
 * returns viseme timings on either the streaming or the synthesis path — so the
 * distribution has to imitate real speech rhythm rather than letter counts.
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

  const chars = Array.from(text);
  // Nothing pronounceable → nothing to animate, pauses alone are silence.
  if (!chars.some(isSpeakable)) return [];

  const slots = chars.map(speakingTime);
  const totalSlots = slots.reduce((sum, slot) => sum + slot, 0);
  if (totalSlots <= 0) return [];
  const msPerSlot = durationMs / totalSlots;

  const events: VisemeEvent[] = [];
  let cursorMs = 0;
  let pauseStartMs = 0;
  let pauseMs = 0;

  // Consecutive punctuation ("...", ".\n\n") is one breath, not four closures.
  const flushPause = () => {
    if (pauseMs <= 0) return;
    pushOrMerge(events, {
      timeMs: startMs + pauseStartMs,
      durationMs: pauseMs,
      mouth: "closed",
      weight: 0.05,
    });
    pauseMs = 0;
  };

  chars.forEach((char, index) => {
    const duration = slots[index] * msPerSlot;
    const timeMs = startMs + cursorMs;
    cursorMs += duration;
    if (duration <= 0) return;

    if (char === " " || char === "\t") return;

    if (isPauseChar(char)) {
      if (pauseMs === 0) pauseStartMs = cursorMs - duration;
      pauseMs += duration;
      return;
    }

    flushPause();
    const last = events[events.length - 1];

    if (isDevanagariConsonant(char)) {
      // Consonant carries an inherent "a" (schwa) → open mouth
      pushOrMerge(events, { timeMs, durationMs: duration, mouth: "aa", weight: 0.9 });
    } else if (char === DEVANAGARI_VIRAMA) {
      // Virama kills the inherent vowel → mouth closes
      pushOrMerge(events, { timeMs, durationMs: duration, mouth: "closed", weight: 0.05 });
    } else if (DEVANAGARI_MATRAS[char]) {
      // Matra reshapes the syllable it attaches to and its time slot belongs
      // to that syllable's vowel, so the event extends through both slots.
      if (last) {
        last.mouth = DEVANAGARI_MATRAS[char];
        last.durationMs += duration;
      }
    } else if (DEVANAGARI_INDEPENDENT_VOWELS[char]) {
      pushOrMerge(events, {
        timeMs,
        durationMs: duration,
        mouth: DEVANAGARI_INDEPENDENT_VOWELS[char],
        weight: 1.0,
      });
    } else if (DEVANAGARI_NASALS.has(char)) {
      // Nasal marks color the previous syllable; no separate opening
      if (last) {
        last.weight = Math.min(1, last.weight + 0.1);
        last.durationMs += duration;
      }
    } else {
      const mouth = charToMouth(char);
      if (mouth) {
        pushOrMerge(events, {
          timeMs,
          durationMs: duration,
          mouth,
          weight: mouth === "closed" ? 0.05 : mouth === "aa" ? 1.0 : 0.75,
        });
      }
    }
  });

  // Trailing punctuation still occupies the end of the clip; let the mouth rest
  // through it instead of pretending the audio stopped early.
  flushPause();

  return events;
}

export function normalizeProviderVisemeEvents(
  providerEvents: VisemeEvent[] | null | undefined,
  durationMs: number,
  startMs = 0,
): VisemeEvent[] {
  if (!providerEvents?.length || durationMs <= 0) return [];
  const validMouths = new Set<VrmMouth>(["aa", "ih", "ou", "ee", "oh", "closed"]);
  return providerEvents
    .filter((event) => validMouths.has(event.mouth))
    .map((event) => {
      const timeMs = startMs + Math.max(0, Math.min(durationMs, event.timeMs));
      const remainingMs = Math.max(0, startMs + durationMs - timeMs);
      return {
        timeMs,
        durationMs: Math.max(16, Math.min(remainingMs || 16, event.durationMs)),
        mouth: event.mouth,
        weight: Math.max(0, Math.min(1, event.weight)),
      };
    })
    .sort((a, b) => a.timeMs - b.timeMs);
}

export function createLipSyncTimeline({
  text = "",
  durationMs,
  startMs = 0,
  providerEvents,
}: LipSyncTimelineInput): VisemeEvent[] {
  const providerTimeline = normalizeProviderVisemeEvents(providerEvents, durationMs, startMs);
  if (providerTimeline.length > 0) return providerTimeline;
  return textToVisemeEvents(text, durationMs, startMs);
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
