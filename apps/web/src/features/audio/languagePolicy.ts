import type { ActiveLanguagePolicy } from "../settings/types/settings";

export type ConversationLocale = "ne-NP" | "hi-IN" | "en-US" | "mixed";

/** Ambiguous script alone is not evidence of Nepali versus Hindi. */
export function resolveConversationLocale(text: string, policy: ActiveLanguagePolicy): ConversationLocale {
  if (policy === "ne-NP" || policy === "hi-IN" || policy === "en-US") return policy;
  if (policy === "ne-en") return "ne-NP";
  if (policy === "hi-en") return "hi-IN";
  if (!/[\u0900-\u097F]/.test(text)) return "mixed";
  if (/(?:मलाई|तपाईं|तिमी|गर्नुहोस्|हुनुहोस्|हाम्रो|मेरो|छैन|छन्|छु)/u.test(text)) return "ne-NP";
  if (/(?:मुझे|तुम्हें|आपका|हूँ|हैं|चाहिए|कृपया)/u.test(text)) return "hi-IN";
  return "mixed";
}

export function recognitionLocale(policy: ActiveLanguagePolicy): ConversationLocale {
  if (policy === "ne-NP" || policy === "ne-en") return "ne-NP";
  if (policy === "hi-IN" || policy === "hi-en" || (policy as string) === "auto-hi-en" || (policy as string) === "auto") return "hi-IN";
  return policy === "en-US" ? "en-US" : "hi-IN";
}

export function browserSpeechLocale(text: string, policy: ActiveLanguagePolicy): string {
  const locale = resolveConversationLocale(text, policy);
  return locale === "mixed" ? (/[\u0900-\u097F]/u.test(text) ? "hi-IN" : "en-US") : locale;
}
