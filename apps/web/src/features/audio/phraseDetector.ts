export interface PhraseDetectorOptions {
  maxBufferChars: number;
  minPhraseChars: number;
  earlyFirstPhrase?: boolean;
}

const DEFAULTS: PhraseDetectorOptions = {
  maxBufferChars: 160,
  minPhraseChars: 12,
  earlyFirstPhrase: false,
};

const SENTENCE_END = /[.!?।…]\s+/;
const SAFE_SOFT_BREAK = /[,;:]\s+/;

/**
 * Incremental stable-phrase detector for progressive TTS.
 * Preserves Unicode/Devanagari and avoids naive splits of technical tokens.
 */
export class PhraseDetector {
  private buffer = "";
  private phraseCount = 0;
  private readonly options: PhraseDetectorOptions;

  constructor(options: Partial<PhraseDetectorOptions> = {}) {
    this.options = { ...DEFAULTS, ...options };
  }

  reset(): void {
    this.buffer = "";
    this.phraseCount = 0;
  }

  pending(): string {
    return this.buffer;
  }

  push(delta: string): string[] {
    if (!delta) return [];
    this.buffer += delta;
    const phrases: string[] = [];

    while (true) {
      const hard = this.buffer.search(SENTENCE_END);
      if (hard >= 0 && hard < this.options.maxBufferChars) {
        const end =
          hard + (this.buffer.slice(hard).match(SENTENCE_END)?.[0].length ?? 1);
        const phrase = this.buffer.slice(0, end).trim();
        this.buffer = this.buffer.slice(end);
        if (
          phrase.length >= this.options.minPhraseChars ||
          /[.!?।…]$/.test(phrase)
        ) {
          this.phraseCount++;
          phrases.push(phrase);
        } else {
          this.buffer = `${phrase} ${this.buffer}`.trimStart();
        }
        continue;
      }

      if (this.options.earlyFirstPhrase && this.phraseCount === 0) {
        const softMatch = this.buffer.slice(0, this.options.maxBufferChars).match(SAFE_SOFT_BREAK);
        if (softMatch && softMatch.index !== undefined) {
          const cut = softMatch.index + softMatch[0].length;
          if (cut >= this.options.minPhraseChars) {
            const phrase = this.buffer.slice(0, cut).trim();
            this.buffer = this.buffer.slice(cut).trimStart();
            if (phrase) {
              this.phraseCount++;
              phrases.push(phrase);
              continue;
            }
          }
        }
      }

      if (this.buffer.length >= this.options.maxBufferChars) {
        const soft = this.findSoftBreak(this.buffer);
        const cut =
          soft > this.options.minPhraseChars
            ? soft
            : this.options.maxBufferChars;
        const phrase = this.buffer.slice(0, cut).trim();
        this.buffer = this.buffer.slice(cut).trimStart();
        if (phrase) {
          this.phraseCount++;
          phrases.push(phrase);
        }
        continue;
      }
      break;
    }
    return phrases;
  }

  flush(): string[] {
    const leftover = this.buffer.trim();
    this.buffer = "";
    return leftover ? [leftover] : [];
  }

  private findSoftBreak(text: string): number {
    // Avoid splitting inside paths, URLs, env vars, decimals.
    const candidate = text.slice(0, this.options.maxBufferChars).search(SAFE_SOFT_BREAK);
    if (candidate < 0) {
      const space = text.lastIndexOf(" ", this.options.maxBufferChars);
      return space > this.options.minPhraseChars ? space : -1;
    }
    const slice = text.slice(0, candidate);
    if (
      /(https?:\/\/\S*|file:\/\/\S*|[A-Za-z]:\\|\.[0-9]+$|[A-Z_]{2,}=)$/i.test(
        slice,
      )
    )
      return -1;
    if (/\S+\.\w{1,4}$/i.test(slice)) return -1;
    return (
      candidate +
      (text.slice(candidate).match(SAFE_SOFT_BREAK)?.[0].length ?? 1)
    );
  }
}
