import type { CompanionState } from "../companion/types";

export type CompanionExpressionIntent =
  | "celebratory"
  | "joyful"
  | "playful"
  | "flirty_warm"
  | "curious"
  | "thinking"
  | "surprised"
  | "empathetic"
  | "concerned"
  | "pouting"
  | "laughing"
  | "confident"
  | "warm"
  // Extended range — the vocabulary a real face actually has
  | "excited"
  | "shy"
  | "sad"
  | "grateful"
  | "determined"
  | "smug"
  | "nervous"
  | "sleepy"
  | "awe"
  | "neutral";

export type ScenarioArchetype =
  | "casual_bro"
  | "affectionate_babe"
  | "playful_sassy"
  | "inquisitive_curious"
  | "intellectual_focused"
  | "celebratory_hype"
  | "comforting_warm"
  | "feisty_pout"
  | "laughing_fun"
  | "confident_reassuring"
  | "shy_flustered"
  | "serene_cozy"
  | "determined_focus"
  | "melancholy_soft"
  | "nervous_awkward"
  | "peaceful_companion";

/** Comprehensive multi-language & emoji pattern catalog for expressive anime facial acting. */
const TERMS: Record<Exclude<CompanionExpressionIntent, "neutral">, RegExp> = {
  celebratory: /(\bcongratulations\b|\bcongrats\b|\bamazing\b|\bwonderful\b|great news|proud of you|\byay\b|\bcelebrate\b|\bshabash\b|bahut acch[haei]|कमाल|बहुत अच्छा|शाबाश|बधाई|victory|\bhurray\b|\bhooray\b|\bcheers\b|we did it|bravo|[🎉🎊🏆🍾🥳🥂])/iu,
  laughing: /(\bhahaha+\b|\bhehehe+\b|\blol\b|\brofl\b|\blmao\b|hilarious|cracking up|that's funny|हँसी|लोल|[😂🤣😹😆])/iu,
  playful: /(\bjust kidding\b|\bteasing\b|\bsilly\b|\bwink\b|\bsmirk\b|\bbusted\b|\bcaught you\b|\bpeekaboo\b|\byou bet\b|\bcheeky\b|\bnaughty\b|मजाक|बदमाश|[😜🤪😋😉😏🤭😈])/iu,
  flirty_warm: /(\bdarling\b|\bsweetheart\b|\bcutie\b|\bhandsome\b|\bgorgeous\b|\bmy love\b|\bhug\b|\bcuddle\b|\bkiss\b|\bblush\b|\bjaan\b|जान|प्यारे|प्यार|मेरी जान|[🥰😘😻💓💘🌹])/iu,
  pouting: /(\bhmph\b|not fair|\bpout\b|\bmean\b|fine then|excuse me|how dare|you meanie|नखरे|गुस्सा|[😤😾😠😒🙄])/iu,
  surprised: /(\bwow\b|\bwhoa\b|\bunbelievable\b|\bno way\b|\bomg\b|mind blown|shocking|astonishing|अरे वाह|सच में|गजब|हैरान|[😲😮😱🤯⚡])/iu,
  curious: /(\bcurious\b|\bwonder\b|what if|tell me more|how come|fascinating|interested to know|\bquestion\b|would you like|shall we|what do you think|want to|क्या|बताओ|चाहोगे|कैसा|[🧐🔍❓❔])/iu,
  thinking: /(\bhmm+\b|let's see|thinking|pondering|evaluating|analyzing|calculating|considering|soch|सोच|विचार|[🤔💭🧠💡])/iu,
  empathetic: /\b(sorry|i understand|i'm here|take your time|that sounds hard|careful|i hear you|it's okay|breathe|don't worry|मुझे समझ|मैं यहाँ हूँ|चिंता मत|आराम से)\b|[🥺🫂🤍🕊️🩹]/iu,
  concerned: /\b(error|failed|problem|issue|careful|warning|cannot|could not|unable|danger|alarm|गलती|समस्या|सावधान|खतरा|नहीं हो पाया)\b|[⚠️🚨😟😰🌧️]/iu,
  confident: /(\bleave it to me\b|\bi got this\b|\beasy peasy\b|\btrust me\b|\bno problem\b|\bof course\b|\babsolutely\b|\bhandled\b|\bperfect\b|\bokay\b|\bok\b|\bbro\b|\bdude\b|\bbhai\b|\byaar\b|\balright\b|हो जाएगा|पक्का|बेफिक्र|[😎💪👑💯])/iu,
  joyful: /(\bhapp(?:y|ier|iest)\b|\bglad\b|\bdelighted\b|love this|\bawesome\b|\bbrilliant\b|\bsuper\b|खुश|प्रसन्न|बढ़िया|[😊😃😄😁🌟💖💕🌸])/iu,
  warm: /\b(hey|hello|love|babe|dear|happy to help|ready to help|welcome|सुनो|नमस्ते|मदद)\b/iu,
  // Extended range — evaluated after the classic set so legacy behaviour is preserved
  excited: /(\bexcited\b|can't wait|\bstoked\b|\bpumped\b|\bhyped\b|\bthrilled\b|\blooking forward\b|उत्साहित|मज्जा आएगा|[🤩🎆🎇])/iu,
  shy: /(\bshy\b|\bembarrassed\b|\bblushing\b|\bflustered\b|\btimid\b|\bbashful\b|शर्मा|लाज|लजाए|[😳🙈☺️])/iu,
  sad: /(\bsad\b|\bheartbroken\b|\bdepressed\b|\btears\b|\bcrying\b|\bmiss you\b|\blonely\b|दुखी|उदास|रोए|रुन|[😢😭💔🥀])/iu,
  grateful: /(\bthank you\b|\bthanks\b|\bthank\b|\bgrateful\b|\bappreciated?\b|\bthankful\b|धन्यवाद|शुक्रिया|आभार|[🙏💐])/iu,
  determined: /(\bdetermined\b|never give up|\bcommitted\b|\bgrind\b|\bno matter what\b|\bi will\b|\bwe will\b|हिम्मत|जिद्द|पक्का गर्ने|[🔥🎯])/iu,
  smug: /(\bsmug\b|told you|called it|\bobviously\b|\bi knew it\b|\bof course i did\b|देखा|[😼])/iu,
  nervous: /(\bnervous\b|\banxious\b|\bawkward\b|\bsweating\b|\bscared\b|\bworried\b|घबरा|डर|[😅😬🥴])/iu,
  sleepy: /(\bsleepy\b|\btired\b|\byawn\b|\bsleep\b|\bcozy\b|\bexhausted\b|\brest\b|निद्रा|सुत्न|थकित|[😴🥱🌙])/iu,
  awe: /(\bawe\b|\bmajestic\b|\bbreathtaking\b|\bmagnificent\b|\bstunning\b|अद्भुत|अत्यन्तै राम्रो|[🌌🌠])/iu,
};

/** Plan emotion keyword mapping to ensure assistant plan intents translate into high-level expressions. */
const PLAN_EMOTION_MAP: Record<string, CompanionExpressionIntent> = {
  happy: "joyful",
  excited: "excited",
  playful: "playful",
  shy: "shy",
  flirty: "flirty_warm",
  curious: "curious",
  thinking: "thinking",
  surprised: "surprised",
  empathetic: "empathetic",
  concerned: "concerned",
  pouting: "pouting",
  laughing: "laughing",
  confident: "confident",
  warm: "warm",
  sad: "sad",
  grateful: "grateful",
  thankful: "grateful",
  determined: "determined",
  focused: "determined",
  smug: "smug",
  nervous: "nervous",
  sleepy: "sleepy",
  tired: "sleepy",
  cozy: "sleepy",
  awe: "awe",
  neutral: "neutral",
};

/**
 * Expression director for Hina's 3D avatar.
 * Evaluates semantic content, emoji markers, punctuation rhythm, companion state,
 * and optional assistant plan directives into lifelike facial acting intents.
 */
export function expressionIntentFor(
  text: string | undefined,
  state: CompanionState,
  planEmotion?: string,
): CompanionExpressionIntent {
  if (state === "error") return "concerned";

  // If the assistant plan explicitly targeted an emotion, honour it first
  if (planEmotion && PLAN_EMOTION_MAP[planEmotion.toLowerCase()]) {
    return PLAN_EMOTION_MAP[planEmotion.toLowerCase()];
  }

  const sample = text?.trim() ?? "";
  if (sample.length > 0) {
    // Priority order for multi-faceted matching. The classic set is evaluated
    // first so existing behaviour never regresses; the extended range catches
    // the feelings a real face has that the classic set had no name for.
    const evaluationOrder: Array<Exclude<CompanionExpressionIntent, "neutral">> = [
      "celebratory",
      "laughing",
      "pouting",
      "surprised",
      "flirty_warm",
      "playful",
      "empathetic",
      "concerned",
      "confident",
      "curious",
      "thinking",
      "joyful",
      "warm",
      "excited",
      "grateful",
      "shy",
      "sad",
      "determined",
      "smug",
      "nervous",
      "sleepy",
      "awe",
    ];

    for (const intent of evaluationOrder) {
      if (TERMS[intent].test(sample)) return intent;
    }

    // Punctuation dynamics
    if (sample.endsWith("?") || sample.includes("? ")) return "curious";
    if (sample.endsWith("!") && sample.length < 80) return "joyful";
    if (sample.endsWith("...") || sample.includes("... ")) return "thinking";
  }

  // State-driven presence
  if (state === "thinking") return "thinking";
  if (state === "speaking" || state === "listening") return "warm";
  return "neutral";
}

export interface SentenceSegment {
  text: string;
  intent: CompanionExpressionIntent;
  weight: number;
}

/**
 * Splits conversational text into structured sentiment segments across time.
 * Allows Hina's facial expressions to dynamically evolve through each sentence
 * during speech, mirroring lifelike human and anime conversational acting.
 */
export function parseExpressionSegments(
  text: string | undefined,
  state: CompanionState,
  planEmotion?: string,
): SentenceSegment[] {
  if (!text || !text.trim()) {
    return [{ text: "", intent: expressionIntentFor("", state, planEmotion), weight: 1 }];
  }
  const clean = text.trim();
  const rawParts = clean.match(/[^.!?\n;]+(?:[.!?\n;]+[\s\p{Extended_Pictographic}]*)?/gu) || [clean];
  const parts = rawParts.map((p) => p.trim()).filter((p) => p.length > 0);
  if (parts.length === 0) {
    return [{ text: clean, intent: expressionIntentFor(clean, state, planEmotion), weight: 1 }];
  }
  const totalLen = parts.reduce((acc, p) => acc + p.length, 0) || 1;
  return parts.map((part) => ({
    text: part,
    intent: expressionIntentFor(part, state, planEmotion),
    weight: part.length / totalLen,
  }));
}

/**
 * Resolves the active expression intent at a given point in the speech delivery timeline.
 * @param segments Pre-calculated sentence segments
 * @param progressRatio 0.0 to 1.0 progress through speech playback
 */
export function getTemporalIntent(
  segments: SentenceSegment[],
  progressRatio: number,
): CompanionExpressionIntent {
  if (segments.length === 0) return "neutral";
  if (segments.length === 1) return segments[0].intent;
  const clamped = Math.max(0, Math.min(1, progressRatio));
  let accumulated = 0;
  for (const seg of segments) {
    accumulated += seg.weight;
    if (clamped <= accumulated + 0.001) {
      return seg.intent;
    }
  }
  return segments[segments.length - 1].intent;
}

/* ══════════════════════════════════════════════════════════════════════
   INFINITE CONTINUOUS GENERATIVE AFFECTIVE ENGINE
   Computes continuous dimensional coordinates and non-repeating
   deterministic micro-acting signatures across millions of situations.
   ══════════════════════════════════════════════════════════════════════ */

export interface AffectiveProfile {
  intent: CompanionExpressionIntent;
  scenarioArchetype: ScenarioArchetype;
  valence: number;        // -1.0 (sorrow/alarm) to +1.0 (radiant joy)
  arousal: number;        // 0.0 (calm/serene) to 1.0 (ecstatic/shocked)
  playfulness: number;    // 0.0 to 1.0 (teasing/mischievous/smug/fang)
  warmth: number;         // 0.0 to 1.0 (tender affection/intimacy)
  surprise: number;       // 0.0 to 1.0 (wonder/curiosity/sparkle)
  thoughtfulness: number; // 0.0 to 1.0 (deep contemplation/focus)
  pout: number;           // 0.0 to 1.0 (cute anime pout/feisty)
  confidence: number;     // 0.0 to 1.0 (assertive/proud)
  drowsy: number;         // 0.0 to 1.0 (sleepy/cozy, lids at half-mast)

  // Asymmetric micro-acting offsets (eliminates robotic symmetry)
  browAsymmetry: number;       // -0.18 to +0.18
  mouthAsymmetry: number;      // -0.22 to +0.22 (charming smirk tilt)
  eyeApertureVariance: number; // -0.12 to +0.12 (subtle wink/squint difference)
  fangBias: number;            // 0.0 to 0.22 (cute anime fang peek)
  headTiltBias: number;        // -0.14 to +0.14 (affectionate/inquisitive head tilt)
  headNodBias: number;         // 0.0 to 0.12 (conversational affirmative micro-nod)

  // Deterministic scenario fingerprint hash
  scenarioHash: number;
}

/** Non-linear string hash for unique deterministic variance per sentence. */
function hashString(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return hash;
}

/** Deterministic pseudo-random float [0, 1) from hash + offset. */
function pseudoRand(hash: number, offset: number): number {
  const v = Math.sin((hash + offset * 137.21) * 12.9898) * 43758.5453;
  return v - Math.floor(v);
}

/** Detects the high-fidelity scenario archetype from conversational signals. */
function detectScenarioArchetype(text: string, intent: CompanionExpressionIntent): ScenarioArchetype {
  const lower = text.toLowerCase();
  
  // 1. Casual Bro / Buddy style ("perfect, okay, bro", "wassup", "chill")
  if (
    /\b(bro|bhai|yaar|wassup|sup|dude|chill|chilling|perfect|okay|ok|alright|cool|haan|theek hai|got it)\b/i.test(lower) &&
    !/\b(love|kiss|cuddle|blush|darling)\b/i.test(lower)
  ) {
    return "casual_bro";
  }

  // 2. Affectionate Babe / Romantic warmth ("babe", "sweetheart", "meri jaan")
  if (
    /\b(babe|sweetheart|darling|meri jaan|my love|cutie|handsome|kiss|cuddle|blush|pyar|babu)\b/i.test(lower) ||
    intent === "flirty_warm"
  ) {
    return "affectionate_babe";
  }

  // 3. Playful Sassy / Teasing
  if (
    /\b(kidding|silly|teasing|smirk|busted|cheeky|naughty|masti|mazak)\b/i.test(lower) ||
    intent === "playful"
  ) {
    return "playful_sassy";
  }

  // 4. Laughing Fun
  if (intent === "laughing" || /\b(hahaha|hehehe|lol|lmao|rofl|hilarious)\b/i.test(lower)) {
    return "laughing_fun";
  }

  // 5. Feisty Pout
  if (intent === "pouting" || /\b(hmph|not fair|pout|how dare|meanie)\b/i.test(lower)) {
    return "feisty_pout";
  }

  // 6. Celebratory Hype
  if (intent === "celebratory" || /\b(congratulations|congrats|amazing|awesome|yay|victory)\b/i.test(lower)) {
    return "celebratory_hype";
  }

  // 7. Comforting Warmth / Empathy
  if (intent === "empathetic" || /\b(sorry|understand|here for you|it's okay|breathe|don't worry)\b/i.test(lower)) {
    return "comforting_warm";
  }

  // 8. Inquisitive / Curious
  if (intent === "curious" || /\b(what if|wonder|curious|tell me|how come|question)\b/i.test(lower)) {
    return "inquisitive_curious";
  }

  // 9. Intellectual / Focused reasoning
  if (
    /\b(code|debug|algorithm|architecture|function|system|analyze|calculate|logic|why|reason)\b/i.test(lower) ||
    intent === "thinking"
  ) {
    return "intellectual_focused";
  }

  // 10. Confident / Reassuring
  if (intent === "confident") {
    return "confident_reassuring";
  }

  // 11. Shy / Flustered — bashful warmth, lowered gaze energy
  if (intent === "shy" || /\b(shy|embarrassed|blushing|flustered|bashful)\b/i.test(lower)) {
    return "shy_flustered";
  }

  // 12. Serene / Cozy — drowsy, restful, late-night softness
  if (intent === "sleepy" || /\b(sleepy|tired|yawn|cozy|exhausted|rest)\b/i.test(lower)) {
    return "serene_cozy";
  }

  // 13. Determined / Focused — locked-in resolve
  if (intent === "determined" || /\b(determined|never give up|no matter what|committed|grind)\b/i.test(lower)) {
    return "determined_focus";
  }

  // 14. Melancholy — genuine softness for genuinely sad turns
  if (intent === "sad" || /\b(sad|heartbroken|miss you|lonely|crying|tears)\b/i.test(lower)) {
    return "melancholy_soft";
  }

  // 15. Nervous / Awkward — jittery but trying
  if (intent === "nervous" || /\b(nervous|anxious|awkward|scared|worried)\b/i.test(lower)) {
    return "nervous_awkward";
  }

  return "peaceful_companion";
}

/**
 * Computes an infinite, continuous multidimensional affective profile for any
 * text, conversational state, and scenario. No two sentences ever produce identical
 * values, and no two deliveries of the same line do either (occurrence nonce),
 * unlocking millions of subtle anime acting combinations.
 */
export function computeAffectiveProfile(
  text: string | undefined,
  state: CompanionState,
  planEmotion?: string,
  progressRatio: number = 0,
  isSpeaking: boolean = false,
  occurrence: number = 0,
): AffectiveProfile {
  const rawText = text?.trim() ?? "";
  const baseIntent = expressionIntentFor(rawText, state, planEmotion);
  const archetype = detectScenarioArchetype(rawText, baseIntent);
  // Occurrence nonce: a human never delivers the same line with byte-identical
  // micro-acting twice. Folding a per-delivery nonce into the entropy hash keeps
  // every delivery of one utterance stable (no per-frame jitter) while making
  // each re-delivery genuinely different — and it stays deterministic for a
  // fixed occurrence, so tests and trace replays remain reproducible.
  const baseHash = rawText ? hashString(rawText) : 10139042;
  const hash = (baseHash ^ Math.imul((Math.trunc(occurrence) | 0) + 1, 2654435761)) | 0;

  // Base coordinates seeded by scenario archetype
  let valence = 0.20;
  let arousal = 0.32;
  let playfulness = 0.15;
  let warmth = 0.40;
  let surprise = 0.0;
  let thoughtfulness = 0.12;
  let pout = 0.0;
  let confidence = 0.40;
  let drowsy = 0.0;
  let headTiltBias = 0.0;
  let headNodBias = 0.0;

  switch (archetype) {
    case "casual_bro":
      valence = 0.62;
      arousal = 0.38;
      playfulness = 0.45;
      warmth = 0.68;
      confidence = 0.78;
      surprise = 0.0; // NEVER wide-eyed shock when chilling with bro
      headTiltBias = 0.06;
      headNodBias = 0.08;
      break;

    case "affectionate_babe":
      valence = 0.84;
      arousal = 0.42;
      playfulness = 0.52;
      warmth = 0.96;
      confidence = 0.55;
      surprise = 0.0;
      headTiltBias = -0.09; // Tender affectionate head tilt
      break;

    case "playful_sassy":
      valence = 0.78;
      arousal = 0.62;
      playfulness = 0.92;
      warmth = 0.70;
      confidence = 0.65;
      surprise = 0.10;
      headTiltBias = 0.11;
      break;

    case "laughing_fun":
      valence = 0.96;
      arousal = 0.88;
      playfulness = 0.86;
      warmth = 0.65;
      confidence = 0.60;
      headNodBias = 0.09;
      break;

    case "feisty_pout":
      valence = -0.15;
      arousal = 0.48;
      pout = 0.85;
      playfulness = 0.42;
      confidence = 0.50;
      headTiltBias = -0.08;
      break;

    case "celebratory_hype":
      valence = 0.92;
      arousal = 0.86;
      playfulness = 0.68;
      warmth = 0.74;
      confidence = 0.85;
      headNodBias = 0.10;
      break;

    case "comforting_warm":
      valence = 0.32;
      arousal = 0.24;
      warmth = 0.92;
      thoughtfulness = 0.45;
      headTiltBias = 0.07;
      break;

    case "intellectual_focused":
      valence = 0.25;
      arousal = 0.36;
      thoughtfulness = 0.90;
      confidence = 0.72;
      surprise = 0.05;
      headTiltBias = -0.05;
      break;

    case "inquisitive_curious":
      valence = 0.44;
      arousal = 0.48;
      surprise = 0.45; // Gentle inquisitive spark
      thoughtfulness = 0.68;
      warmth = 0.58;
      headTiltBias = 0.10; // Inquisitive head tilt
      break;

    case "confident_reassuring":
      valence = 0.74;
      arousal = 0.55;
      confidence = 0.92;
      warmth = 0.62;
      playfulness = 0.40;
      headNodBias = 0.07;
      break;

    case "shy_flustered":
      // Bashful: warm but looking away, low confidence, gentle fluster energy
      valence = 0.58;
      arousal = 0.46;
      warmth = 0.88;
      playfulness = 0.30;
      confidence = 0.22;
      surprise = 0.08;
      headTiltBias = -0.11;
      break;

    case "serene_cozy":
      // Sleepy/cozy: the slowest, softest she ever gets — lids heavy, all calm
      valence = 0.42;
      arousal = 0.10;
      warmth = 0.82;
      thoughtfulness = 0.30;
      drowsy = 0.78;
      headTiltBias = 0.06;
      break;

    case "determined_focus":
      // Locked in: steady gaze, high confidence, no nonsense
      valence = 0.42;
      arousal = 0.56;
      confidence = 0.96;
      thoughtfulness = 0.62;
      surprise = 0.0;
      headNodBias = 0.05;
      break;

    case "melancholy_soft":
      // Genuine sadness answered with genuine softness, never a painted smile
      valence = -0.42;
      arousal = 0.20;
      warmth = 0.66;
      pout = 0.28;
      confidence = 0.25;
      headTiltBias = -0.06;
      break;

    case "nervous_awkward":
      // Jittery but trying: quick micro-energy, low confidence, warm intent
      valence = 0.12;
      arousal = 0.52;
      confidence = 0.28;
      warmth = 0.54;
      surprise = 0.12;
      headTiltBias = 0.05;
      break;

    default: // peaceful_companion
      if (state === "listening") {
        valence = 0.35; arousal = 0.28; warmth = 0.68; headTiltBias = 0.04;
      } else if (state === "speaking") {
        valence = 0.45; arousal = 0.42; warmth = 0.62;
      } else {
        valence = 0.30; arousal = 0.22; warmth = 0.55;
      }
      break;
  }

  // Sentiment modifier cues from text syntax & punctuation
  if (rawText.includes("!") && archetype !== "feisty_pout") arousal = Math.min(1, arousal + 0.18);
  if (rawText.includes("~")) playfulness = Math.min(1, playfulness + 0.22);
  if (rawText.length > 120) thoughtfulness = Math.min(1, thoughtfulness + 0.15);

  // In-sentence temporal progression while speaking
  if (isSpeaking) {
    const p = Math.max(0, Math.min(1, progressRatio));
    if (p < 0.20) {
      // Opening phrase: attentive forward presence
      thoughtfulness = Math.min(1, thoughtfulness + 0.08);
    } else if (p > 0.80) {
      // Closing phrase: warmth and gentle resolving smile
      warmth = Math.min(1, warmth + 0.12);
      arousal = Math.max(0.15, arousal * 0.88);
    }
  } else if (state === "idle" || state === "listening") {
    // ── LIVING COMPANION IDLE ATTENUATION ─────────────────────────────────────
    // When NOT actively speaking, she relaxes naturally:
    // NO wide-eyed shock, NO speech strain, mouth closed softly, gentle warmth.
    arousal = 0.24;
    surprise = 0.0;
    pout = 0.0;
    warmth = Math.max(0.50, Math.min(0.75, warmth));
    headTiltBias *= 0.5;
  }

  // Continuous micro-acting variance derived from sentence 64-bit entropy hash
  const browAsym = (pseudoRand(hash, 1) - 0.5) * 0.22;
  const mouthAsym = (pseudoRand(hash, 2) - 0.5) * 0.26;
  const eyeAsym = (pseudoRand(hash, 3) - 0.5) * 0.16;
  // Fang peek ONLY during active playful speaking, NEVER when idle or calm
  const fangBias = (isSpeaking && playfulness > 0.55) ? (0.08 + pseudoRand(hash, 4) * 0.14) : 0;
  const headTilt = headTiltBias + (pseudoRand(hash, 5) - 0.5) * 0.08;
  const headNod = headNodBias + pseudoRand(hash, 6) * 0.04;

  return {
    intent: baseIntent,
    scenarioArchetype: archetype,
    valence,
    arousal,
    playfulness,
    warmth,
    surprise,
    thoughtfulness,
    pout,
    confidence,
    drowsy,
    browAsymmetry: browAsym,
    mouthAsymmetry: mouthAsym,
    eyeApertureVariance: eyeAsym,
    fangBias,
    headTiltBias: headTilt,
    headNodBias: headNod,
    scenarioHash: hash,
  };
}

/**
 * Every morph target `computeDirectMorphTargets` can emit. The GPU optimizer's
 * morph prune keeps only morphs bound to named VRM expressions — and none of
 * these have one — so any avatar that drives the rich face must pass this list
 * as `keepMorphNames`, or the prune deletes the whole affective range and the
 * face falls back to the six whole-face presets (measured: "limited
 * expressions" despite the engine computing them every frame).
 */
export const DIRECT_MORPH_KEYS: readonly string[] = [
  "Fcl_EYE_Joy",
  "Fcl_EYE_Joy_R",
  "Fcl_EYE_Joy_L",
  "Fcl_EYE_Surprised",
  "Fcl_BRW_Joy",
  "Fcl_BRW_Fun",
  "Fcl_BRW_Surprised",
  "Fcl_BRW_Sorrow",
  "Fcl_BRW_Angry",
  "Fcl_MTH_Up",
  "Fcl_MTH_Down",
  "Fcl_MTH_SkinFung",
  "Fcl_MTH_SkinFung_R",
  "Fcl_MTH_SkinFung_L",
  "Fcl_HA_Fung1",
  "Fcl_EYE_Sorrow",
  "Fcl_EYE_Fun",
  "Fcl_EYE_Close",
  "Fcl_MTH_Small",
  "Fcl_MTH_Large",
];

/**
 * Computes high-level morph target influences across VRoid's 57 blendshapes.
 * Incorporates continuous affective dimensions, audio stress energy,
 * prime-frequency organic living micro-oscillations, and asymmetric micro-acting.
 */
export function computeDirectMorphTargets(
  profile: AffectiveProfile,
  time: number,
  jawEnergy: number = 0,
  isSpeaking: boolean = false,
): Record<string, number> {
  // Living multi-harmonic organic oscillations (never static, never repeating)
  const organicWave1 = Math.sin(time * 1.83) * Math.sin(time * 0.67 + 0.4);
  const organicWave2 = Math.sin(time * 1.13 + 1.2);
  const organicWave3 = Math.sin(time * 0.79 + 2.1);
  const microFlutter = organicWave1 * 0.025;

  const rawEnergy = Math.min(1, Math.max(0, jawEnergy * 3.2));
  const vocalStress = isSpeaking && rawEnergy > 0.52 ? (rawEnergy - 0.52) * 0.35 : 0;

  const {
    valence,
    arousal,
    playfulness,
    warmth,
    surprise,
    thoughtfulness,
    pout,
    drowsy,
    browAsymmetry,
    mouthAsymmetry,
    eyeApertureVariance,
    fangBias,
  } = profile;

  // 1. Smiling curved eyes (^ _ ^) - warm, genuine anime joy
  // Clamped to a delicate, cute range [0, 0.32] so eyelids curve warmly without pinching shut or deforming
  const baseEyeJoy = Math.min(0.32, Math.max(0,
    warmth * 0.22 +
    (valence > 0 ? valence * 0.18 : 0) +
    playfulness * 0.12 +
    microFlutter
  ));
  // Unilateral asymmetry must be a subtle micro-offset (+- 0.025 max), not an entire second layer
  const eyeJoyR = Math.min(0.34, Math.max(0, baseEyeJoy + eyeApertureVariance * 0.06 + (mouthAsymmetry > 0.05 ? 0.02 : 0)));
  const eyeJoyL = Math.min(0.34, Math.max(0, baseEyeJoy - eyeApertureVariance * 0.06 + (mouthAsymmetry < -0.05 ? 0.02 : 0)));

  // 2. Wide sparkling anime eyes (O _ O)
  // CRITICAL: MUST ONLY activate on genuine high shock while speaking, NEVER for casual questions or idle!
  const eyeSurprised = (isSpeaking && surprise > 0.65 && arousal > 0.70)
    ? Math.min(0.40, (surprise - 0.65) * 1.2 + vocalStress * 0.2)
    : 0;

  // 3. Eyebrows (Asymmetric living micro-acting)
  const baseBrowJoy = valence > 0 ? valence * 0.58 : 0;
  const browJoy = Math.min(0.85, Math.max(0, baseBrowJoy + organicWave2 * 0.02));

  const baseBrowFun = playfulness * 0.55 + (arousal * 0.18);
  const browFun = Math.min(0.85, Math.max(0, baseBrowFun + (browAsymmetry > 0 ? browAsymmetry * 0.4 : 0)));

  const baseBrowSurprised = isSpeaking ? (surprise * 0.45 + (thoughtfulness * 0.20) + vocalStress) : 0;
  const browSurprised = Math.min(0.70, Math.max(0, baseBrowSurprised + (browAsymmetry < 0 ? -browAsymmetry * 0.4 : 0)));

  const browSorrow = Math.min(0.75, Math.max(0,
    (valence < 0 ? (-valence) * 0.55 : 0) +
    pout * 0.30
  ));

  const browAngry = Math.min(0.65, Math.max(0,
    pout * 0.35 +
    (thoughtfulness > 0.75 ? 0.15 : 0) +
    (valence < -0.4 ? 0.20 : 0) +
    // Emphasis furrow: brows knit slightly on stressed syllables — the
    // micro-expression that makes emphatic speech read as felt, not recited.
    (isSpeaking ? vocalStress * 0.30 : 0)
  ));

  // 4. Radiant mouth corners & charming asymmetric smirk
  // When idle: gentle closed-lip resting smile (0.12..0.18 + slow living wave)
  const idleRestingSmile = 0.14 + organicWave3 * 0.025;
  const baseMouthUp = isSpeaking
    ? Math.min(0.85, Math.max(0,
        warmth * 0.36 +
        playfulness * 0.32 +
        (valence > 0 ? valence * 0.40 : 0) +
        0.25 +
        organicWave3 * 0.02
      ))
    : idleRestingSmile;

  const mouthDown = Math.min(0.75, Math.max(0,
    pout * 0.55 +
    (valence < -0.2 ? (-valence) * 0.38 : 0)
  ));

  // 5. Cute anime fang peek (Fcl_MTH_SkinFung_R/L)
  // Clamped and ONLY active during active speaking in playful moments
  const fangR = (isSpeaking && playfulness > 0.50)
    ? Math.min(0.22, Math.max(0,
        fangBias +
        (mouthAsymmetry > 0 ? mouthAsymmetry * 0.25 : 0)
      ))
    : 0;
  const fangL = (isSpeaking && playfulness > 0.50 && mouthAsymmetry < -0.06)
    ? Math.min(0.20, Math.max(0, -mouthAsymmetry * 0.25))
    : 0;

  // 6. Upper teeth smile peek (Fcl_HA_Fung1)
  // ONLY for genuine laughing while speaking, strictly ZERO when idle
  const teethPeek = (isSpeaking && valence > 0.75 && playfulness > 0.70) ? 0.22 : 0;

  // ── EXTENDED RANGE MORPHS ────────────────────────────────────────────
  // Every key below is ALWAYS present in the returned dict (0 when inactive):
  // the renderer eases toward whatever the dict says, and a key that vanished
  // mid-emotion would freeze on the face instead of decaying away.

  // 7. Sorrow eyes (Fcl_EYE_Sorrow) — droopy upper lids for genuinely low valence
  const eyeSorrow = Math.min(0.68, Math.max(0,
    (valence < -0.1 ? (-valence) * 0.52 : 0) +
    pout * 0.22
  ));

  // 8. Fun crescent eyes (Fcl_EYE_Fun) — gentle charming accent [0, 0.16]
  const eyeFun = Math.min(0.16, Math.max(0,
    playfulness * 0.18 +
    (isSpeaking ? warmth * 0.05 : 0) +
    microFlutter * 0.2
  ));

  // 9. Heavy lids (Fcl_EYE_Close) — capped so it doesn't block blinks [0, 0.28]
  const eyeClose = Math.min(0.28, Math.max(0,
    drowsy * 0.28 + organicWave2 * 0.02 * drowsy
  ));

  // 10. Small calm mouth (Fcl_MTH_Small) — pursed, composed, thoughtful
  const mouthSmall = (!isSpeaking || thoughtfulness > 0.6)
    ? Math.min(0.40, Math.max(0, (1 - arousal) * thoughtfulness * 0.34 + drowsy * 0.12))
    : 0;

  // 11. Big open smile (Fcl_MTH_Large) — radiant celebratory/laughing grin
  const mouthLarge = (isSpeaking && valence > 0.70 && arousal > 0.62)
    ? Math.min(0.62, (valence - 0.70) * 1.1 + (arousal - 0.62) * 0.6)
    : 0;

  return {
    Fcl_EYE_Joy: baseEyeJoy,
    Fcl_EYE_Joy_R: eyeJoyR,
    Fcl_EYE_Joy_L: eyeJoyL,
    Fcl_EYE_Surprised: eyeSurprised,
    Fcl_BRW_Joy: browJoy,
    Fcl_BRW_Fun: browFun,
    Fcl_BRW_Surprised: browSurprised,
    Fcl_BRW_Sorrow: browSorrow,
    Fcl_BRW_Angry: browAngry,
    Fcl_MTH_Up: baseMouthUp,
    Fcl_MTH_Down: mouthDown,
    Fcl_MTH_SkinFung: Math.max(fangR, fangL),
    Fcl_MTH_SkinFung_R: fangR,
    Fcl_MTH_SkinFung_L: fangL,
    Fcl_HA_Fung1: teethPeek,
    Fcl_EYE_Sorrow: eyeSorrow,
    Fcl_EYE_Fun: eyeFun,
    Fcl_EYE_Close: eyeClose,
    Fcl_MTH_Small: mouthSmall,
    Fcl_MTH_Large: mouthLarge,
  };
}
