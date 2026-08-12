import type { CompanionState } from "../companion/types";

export type CompanionExpressionIntent = "neutral" | "warm" | "curious" | "empathetic" | "celebratory" | "concerned";

const TERMS: Record<Exclude<CompanionExpressionIntent, "neutral">, RegExp> = {
  celebratory: /(\bcongratulations\b|\bcongrats\b|\bamazing\b|\bwonderful\b|great news|proud of you|\byay\b|\bcelebrate\b|\bshabash\b|bahut acch[haei]|कमाल|बहुत अच्छा|शाबाश)/i,
  empathetic: /\b(sorry|i understand|i'm here|take your time|that sounds hard|careful|i hear you|मुझे समझ|मैं यहाँ हूँ|चिंता मत|आराम से)\b/i,
  concerned: /\b(error|failed|problem|issue|careful|warning|cannot|could not|unable|गलती|समस्या|सावधान|नहीं हो पाया)\b/i,
  curious: /\b(question|would you like|shall we|tell me|what do you think|want to|क्?या|बताओ|चाहोगे)\b/i,
  warm: /\b(hey|hello|love|babe|dear|happy to help|ready to help|सुनो|प्यारे|जान|मदद)\b/i,
};

/** A deterministic, private text cue—not emotion recognition or camera analysis. */
export function expressionIntentFor(text: string | undefined, state: CompanionState): CompanionExpressionIntent {
  if (state === "error") return "concerned";
  const sample = text?.trim() ?? "";
  for (const intent of ["celebratory", "empathetic", "concerned", "curious", "warm"] as const) {
    if (TERMS[intent].test(sample)) return intent;
  }
  return state === "speaking" || state === "listening" ? "warm" : "neutral";
}
