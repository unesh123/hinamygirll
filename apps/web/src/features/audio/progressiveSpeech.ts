export interface SpeechAudio { blob: Blob; provider: string; latencyMs: number }
interface Phrase { text: string; audio?: Promise<SpeechAudio | null> }
interface Options {
  synthesize: (text: string, signal: AbortSignal) => Promise<SpeechAudio | null>;
  play: (text: string, audio: SpeechAudio | null, signal: AbortSignal) => Promise<void>;
  onError?: (error: unknown) => void;
}

/** Prefetch two phrases while speaking, preserve order, and cancel the whole turn. */
export class ProgressiveSpeech {
  private readonly abort = new AbortController();
  private readonly pending: Phrase[] = [];
  private running = false;
  private count = 0;
  private readonly options: Options;
  constructor(options: Options) { this.options = options; }
  get hasPhrases() { return this.count > 0; }
  enqueue(text: string) {
    if (this.abort.signal.aborted || !text.trim()) return;
    this.count += 1;
    this.pending.push({ text: text.trim() });
    this.prepare();
    void this.drain();
  }
  cancel() { this.abort.abort(); this.pending.length = 0; }
  private prepare() {
    for (const phrase of this.pending.slice(0, 2)) {
      if (!phrase.audio) {
        phrase.audio = this.options.synthesize(phrase.text, this.abort.signal).catch((err) => {
          console.warn("[HINAA] Progressive speech synthesis chunk error:", err);
          return null;
        });
      }
    }
  }
  private async drain() {
    if (this.running) return;
    this.running = true;
    try {
      while (this.pending.length && !this.abort.signal.aborted) {
        const phrase = this.pending.shift()!;
        this.prepare();
        const audio = await phrase.audio;
        if (this.abort.signal.aborted) break;
        await this.options.play(phrase.text, audio ?? null, this.abort.signal);
      }
    } catch (error) {
      if (!this.abort.signal.aborted) this.options.onError?.(error);
      this.cancel();
    } finally { this.running = false; }
  }
}
