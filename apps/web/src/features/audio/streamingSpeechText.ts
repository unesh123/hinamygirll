import { PhraseDetector } from "./phraseDetector";

export function cleanSpeechText(text: string): string {
  return text.replace(/<(?:think|thought)>[\s\S]*?<\/(?:think|thought)>/gi, "")
    .replace(/<(?:think|thought)>[\s\S]*$/gi, "")
    .replace(/```[\s\S]*?```/g, "").replace(/```[\s\S]*$/g, "")
    .replace(/!?\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/^\s*#{1,6}\s+/gm, "").replace(/^\s*[-*+>]\s+/gm, "")
    .replace(/[*_~`|]/g, "");
}

/** Speak only stable user-visible text; final plans cannot replay streamed phrases. */
export class StreamingSpeechText {
  private previous = "";
  private lastPhrase = "";
  private detector = new PhraseDetector({ maxBufferChars: 120, minPhraseChars: 12, earlyFirstPhrase: true });
  push(visibleText: string): string[] {
    const clean = cleanSpeechText(visibleText);
    if (!clean.startsWith(this.previous)) return [];
    const delta = clean.slice(this.previous.length);
    this.previous = clean;
    return this.uniqueAdjacent(this.detector.push(delta));
  }
  flush() { return this.uniqueAdjacent(this.detector.flush()); }
  private uniqueAdjacent(phrases: string[]) {
    return phrases.filter(phrase => {
      const normalized = phrase.toLocaleLowerCase().replace(/\s+/g, " ").trim();
      if (normalized === this.lastPhrase) return false;
      this.lastPhrase = normalized;
      return true;
    });
  }
}
