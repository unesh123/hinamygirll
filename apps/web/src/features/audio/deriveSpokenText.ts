/**
 * Produce a concise, speech-safe fallback when a provider does not return the
 * dedicated `spokenText` field. Rich `displayText` is never modified.
 */
let fallbackDerived = false;

const MAX_SPOKEN_LENGTH = 280;
const CONTINUATION_HINT = "Details are available in the chat.";
const ABBREVIATIONS = new Set([
  "dr.",
  "mr.",
  "mrs.",
  "ms.",
  "prof.",
  "sr.",
  "jr.",
  "st.",
  "vs.",
  "etc.",
  "e.g.",
  "i.e.",
]);

function isSentenceBoundary(text: string, punctuationIndex: number): boolean {
  const punctuation = text[punctuationIndex];
  if (!".!?।".includes(punctuation)) return false;
  const next = text[punctuationIndex + 1];
  if (next && !/\s/.test(next)) return false;

  if (punctuation === ".") {
    const prefix = text.slice(0, punctuationIndex + 1);
    const token = prefix.match(/(?:^|\s)(\S+)$/)?.[1]?.toLowerCase() ?? "";
    if (ABBREVIATIONS.has(token) || /^[a-z]\.$/i.test(token)) return false;
  }
  return true;
}

function truncateForSpeech(text: string): string {
  const preferredLimit = MAX_SPOKEN_LENGTH - CONTINUATION_HINT.length - 1;
  let boundary = -1;
  for (let index = 0; index < Math.min(text.length, preferredLimit); index += 1) {
    if (isSentenceBoundary(text, index)) boundary = index + 1;
  }

  let summary: string;
  if (boundary >= 40) {
    summary = text.slice(0, boundary).trim();
  } else {
    const windowText = text.slice(0, preferredLimit);
    const wordBoundary = windowText.lastIndexOf(" ");
    summary = (wordBoundary >= 40 ? windowText.slice(0, wordBoundary) : windowText).trim();
    if (summary && !/[.!?।:]$/.test(summary)) summary += ".";
  }
  return `${summary} ${CONTINUATION_HINT}`.trim();
}

const META_REFLECTION_RE = /^\s*(?:the (?:instructions|system prompt|developer instructions|prompt) (?:are|say|states?|requires?|dictates?|strictly)|instructions (?:are|require|say|state)|turn \d+\+?(?:\s+only)?\s*:|turn \d+\+? means|unesh (?:just|is|has|asked|said|wants|did not|didn't)|(?:the )?user (?:just|is|has|asked|said|wants|did not|didn't)|i must (?:not )?(?:repeat|greet|answer|dive|respond|provide)|i should (?:not )?(?:force-feed|repeat|ask|give|respond)|my (?:persona|identity|character|task|goal) (?:is|requires)|acting as (?:hina|hinaa|companion)|character guidelines|(?:his|the) active topic is|(?:goal|plan|internal reasoning|reasoning|thinking|scratchpad)\s*:|analyzing (?:user|the prompt|request|context)|let (?:me|us) analyze|current turn\s*:)\b/im;

export function deriveSpokenText(rawText: string): string {
  if (!rawText) return "";
  fallbackDerived = true;

  // First strip thinking blocks entirely before generic tag stripping
  let cleaned = rawText
    .replace(/<(?:think|thought)>[\s\S]*?<\/(?:think|thought)>/gi, "")
    .replace(/<(?:think|thought)>[\s\S]*$/gi, "")
    .replace(/<\/(?:think|thought)>/gi, "");

  // Strip prompt meta-reflection lines
  const lines = cleaned.split("\n").filter((line) => !META_REFLECTION_RE.test(line.trim()));
  cleaned = lines.join(" ");

  const spoken = cleaned
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]+\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\[\^[a-zA-Z0-9_-]+\]/g, "")
    .replace(/\[\d+\]/g, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/[*_]{1,3}/g, "")
    .replace(/^\s*[-*+•]\s+/gm, "")
    .replace(/^\|.*\|\s*$/gm, "")
    .replace(/^\|?\s*[-:]+\s*(\|\s*[-:]+\s*)*\|?\s*$/gm, "")
    .replace(/^[-*_]{3,}\s*$/gm, "")
    .replace(/^>\s*/gm, "")
    .replace(/<[^>]+>/g, "")
    .replace(/(?:Topic|Format|Scope|Output):\s*[^.\n]+(?:\n|$)/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  return spoken.length <= MAX_SPOKEN_LENGTH ? spoken : truncateForSpeech(spoken);
}

export function wasSpokenTextDerived(): boolean {
  return fallbackDerived;
}
