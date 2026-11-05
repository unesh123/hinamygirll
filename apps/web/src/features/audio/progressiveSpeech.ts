import type { VisemeEvent } from "./textToViseme";

export interface SpeechAudio {
  blob: Blob;
  provider: string;
  latencyMs: number;
  stream?: AsyncIterable<SpeechAudio>;
  text?: string;
  /** Vendor-timed mouth shapes for this clip (relative to clip start). */
  visemes?: VisemeEvent[];
}
interface Phrase { text: string; idempotencyKey?: string; audio?: Promise<SpeechAudio | null> }
interface Options {
  synthesize: (text: string, signal: AbortSignal) => Promise<SpeechAudio | null>;
  play: (text: string, audio: SpeechAudio | null, signal: AbortSignal) => Promise<void>;
  onError?: (error: unknown) => void;
  generationId?: number;
}

/** Prefetch two phrases while speaking, preserve order, cancel the whole turn, and prevent duplicate playback. */
export class ProgressiveSpeech {
  private readonly abort = new AbortController();
  private readonly pending: Phrase[] = [];
  private readonly enqueuedKeys = new Set<string>();
  private running = false;
  private count = 0;
  private currentGenerationId: number;
  private readonly options: Options;

  constructor(options: Options) {
    this.options = options;
    this.currentGenerationId = options.generationId ?? 1;
  }

  get hasPhrases() { return this.count > 0; }
  get generationId() { return this.currentGenerationId; }

  enqueue(text: string, idempotencyKey?: string, generationId?: number): boolean {
    if (this.abort.signal.aborted || !text.trim()) return false;
    if (generationId !== undefined && generationId < this.currentGenerationId) {
      console.warn(`[HINAA] Stale generation ${generationId} < ${this.currentGenerationId} dropped`);
      return false;
    }
    const cleanKey = idempotencyKey || text.trim().toLowerCase();
    if (this.enqueuedKeys.has(cleanKey)) {
      console.info(`[HINAA] Duplicate segment dropped by idempotency key: ${cleanKey}`);
      return false;
    }
    this.enqueuedKeys.add(cleanKey);
    this.count += 1;
    this.pending.push({ text: text.trim(), idempotencyKey: cleanKey });
    this.prepare();
    void this.drain();
    return true;
  }

  advanceGeneration(newGenerationId: number) {
    this.currentGenerationId = newGenerationId;
    this.cancel();
  }

  cancel() {
    this.abort.abort();
    this.pending.length = 0;
  }

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
