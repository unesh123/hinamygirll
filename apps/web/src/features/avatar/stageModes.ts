/**
 * stageModes.ts — pure detectors for the cinematic stage's dynamic modes.
 *
 *  - Code mode: when she explains code, the camera pulls wider, she steps
 *    left, and a real editor panel unfolds on the right.
 *  - OtakuXWear chamber: when the topic is her premium anime-commerce brand,
 *    the chamber subtly transforms into that theme.
 *
 * Framework-free so both are unit-testable.
 */

const CODE_FENCE = /```(?:[a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g;

/** Returns the first fenced code block's content, or null when absent. */
export function extractCodeBlock(text: string | null | undefined): string | null {
  if (!text) return null;
  CODE_FENCE.lastIndex = 0;
  const match = CODE_FENCE.exec(text);
  if (!match) return null;
  const body = match[1] ?? "";
  return body.trim().length > 0 ? body.trim() : null;
}

/** True when the text contains at least one fenced code block. */
export function hasCodeBlock(text: string | null | undefined): boolean {
  return extractCodeBlock(text) !== null;
}

/** True when the message talks about the OtakuXWear anime-commerce brand. */
export function isOtakuXWearTopic(text: string | null | undefined): boolean {
  if (!text) return false;
  return /otaku\s*x\s*wear|otakuxwear|otaku wear|anime[- ]?commerce|anime[- ]?(store|merch|shop)/i.test(
    text,
  );
}

/** Splits spoken text into short display phrases (not per-character). */
export function splitIntoPhrases(
  text: string | null | undefined,
  maxLen = 46,
): string[] {
  const trimmed = (text ?? "").trim();
  if (!trimmed) return [];
  const sentences = trimmed
    .split(/(?<=[.!?।…])\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  const phrases: string[] = [];
  for (const sentence of sentences) {
    if (sentence.length <= maxLen || phrases.length === 0) {
      phrases.push(sentence);
      continue;
    }
    // Break long sentences at comma/space boundaries without splitting words.
    const parts = sentence.split(/(?<=[,;:–-])\s+/);
    let current = "";
    for (const part of parts) {
      if ((current + " " + part).trim().length > maxLen && current) {
        phrases.push(current.trim());
        current = part;
      } else {
        current = (current + " " + part).trim();
      }
    }
    if (current) phrases.push(current.trim());
  }
  return phrases.slice(0, 12);
}
