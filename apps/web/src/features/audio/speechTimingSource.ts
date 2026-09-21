import type { VisemeEvent, VrmMouth } from "./textToViseme";
import { getActiveViseme } from "./textToViseme";

export interface TimedWord {
  word: string;
  startMs: number;
  endMs: number;
}

export interface SpeechTimingSource {
  readonly id: string;
  /** Returns current playback offset in milliseconds from the start of the utterance. */
  getPlaybackTime(): number;
  /** Returns total duration in milliseconds. */
  getDuration(): number;
  /** Returns the active word at the specified playback timestamp, or null if in silence/gap. */
  getWordAt(timeMs: number): TimedWord | null;
  /** Returns the active viseme event at the specified playback timestamp, or null. */
  getVisemeAt(timeMs: number): VisemeEvent | null;
  /** Returns true if speech is actively playing. */
  isPlaying(): boolean;
  /** Optional seeking capability. */
  seek?(timeMs: number): void;
}

/** Helper to binary-search timed items like words or visemes. */
export function findActiveTimedItem<T extends { startMs: number; endMs: number }>(
  items: readonly T[],
  timeMs: number
): T | null {
  if (!items.length || timeMs < items[0].startMs || timeMs > items[items.length - 1].endMs) {
    return null;
  }
  let low = 0;
  let high = items.length - 1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    const item = items[mid];
    if (timeMs < item.startMs) {
      high = mid - 1;
    } else if (timeMs > item.endMs) {
      low = mid + 1;
    } else {
      return item;
    }
  }
  return null;
}

export interface SyntheticTimingOptions {
  id?: string;
  durationMs: number;
  words?: TimedWord[];
  visemes?: VisemeEvent[];
  clock?: () => number;
}

export class SyntheticSpeechTimingSource implements SpeechTimingSource {
  readonly id: string;
  private durationMs: number;
  private words: TimedWord[];
  private visemes: VisemeEvent[];
  private clockFn: () => number;
  private playing = false;
  private startClockMs = 0;
  private pausedOffsetMs = 0;

  constructor(options: SyntheticTimingOptions) {
    this.id = options.id ?? `synth-${Math.random().toString(36).slice(2, 8)}`;
    this.durationMs = options.durationMs;
    this.words = options.words ?? [];
    this.visemes = options.visemes ?? [];
    this.clockFn = options.clock ?? (() => performance.now());
  }

  start(): void {
    this.startClockMs = this.clockFn() - this.pausedOffsetMs;
    this.playing = true;
  }

  pause(): void {
    if (this.playing) {
      this.pausedOffsetMs = this.getPlaybackTime();
      this.playing = false;
    }
  }

  stop(): void {
    this.playing = false;
    this.pausedOffsetMs = 0;
    this.startClockMs = 0;
  }

  getPlaybackTime(): number {
    if (!this.playing) return this.pausedOffsetMs;
    const elapsed = this.clockFn() - this.startClockMs;
    return Math.max(0, Math.min(elapsed, this.durationMs));
  }

  getDuration(): number {
    return this.durationMs;
  }

  getWordAt(timeMs: number): TimedWord | null {
    return findActiveTimedItem(this.words, timeMs);
  }

  getVisemeAt(timeMs: number): VisemeEvent | null {
    return getActiveViseme(timeMs, this.visemes);
  }

  isPlaying(): boolean {
    if (!this.playing) return false;
    return this.getPlaybackTime() < this.durationMs;
  }

  seek(timeMs: number): void {
    this.pausedOffsetMs = Math.max(0, Math.min(timeMs, this.durationMs));
    if (this.playing) {
      this.startClockMs = this.clockFn() - this.pausedOffsetMs;
    }
  }
}

export interface AudioElementTimingOptions {
  id?: string;
  audioElement: {
    currentTime: number;
    duration: number;
    paused: boolean;
    ended: boolean;
  };
  words?: TimedWord[];
  visemes?: VisemeEvent[];
  fallbackDurationMs?: number;
}

export class AudioElementSpeechTimingSource implements SpeechTimingSource {
  readonly id: string;
  private audio: AudioElementTimingOptions["audioElement"];
  private words: TimedWord[];
  private visemes: VisemeEvent[];
  private fallbackDurationMs: number;

  constructor(options: AudioElementTimingOptions) {
    this.id = options.id ?? `audio-${Math.random().toString(36).slice(2, 8)}`;
    this.audio = options.audioElement;
    this.words = options.words ?? [];
    this.visemes = options.visemes ?? [];
    this.fallbackDurationMs = options.fallbackDurationMs ?? 0;
  }

  getPlaybackTime(): number {
    return Math.max(0, (this.audio.currentTime || 0) * 1000);
  }

  getDuration(): number {
    const d = this.audio.duration;
    if (Number.isFinite(d) && d > 0) return d * 1000;
    return this.fallbackDurationMs;
  }

  getWordAt(timeMs: number): TimedWord | null {
    return findActiveTimedItem(this.words, timeMs);
  }

  getVisemeAt(timeMs: number): VisemeEvent | null {
    return getActiveViseme(timeMs, this.visemes);
  }

  isPlaying(): boolean {
    return !this.audio.paused && !this.audio.ended && this.getPlaybackTime() < this.getDuration();
  }

  seek(timeMs: number): void {
    this.audio.currentTime = Math.max(0, timeMs / 1000);
  }
}

export interface BrowserSpeechTimingOptions {
  id?: string;
  durationMs: number;
  words?: TimedWord[];
  visemes?: VisemeEvent[];
  clock?: () => number;
}

export class BrowserSpeechTimingSource implements SpeechTimingSource {
  readonly id: string;
  private durationMs: number;
  private words: TimedWord[];
  private visemes: VisemeEvent[];
  private clockFn: () => number;
  private playing = false;
  private startMs = 0;
  private pauseOffsetMs = 0;

  constructor(options: BrowserSpeechTimingOptions) {
    this.id = options.id ?? `browser-${Math.random().toString(36).slice(2, 8)}`;
    this.durationMs = options.durationMs;
    this.words = options.words ?? [];
    this.visemes = options.visemes ?? [];
    this.clockFn = options.clock ?? (() => performance.now());
  }

  onUtteranceStart(): void {
    this.startMs = this.clockFn() - this.pauseOffsetMs;
    this.playing = true;
  }

  onUtterancePause(): void {
    if (this.playing) {
      this.pauseOffsetMs = this.getPlaybackTime();
      this.playing = false;
    }
  }

  onUtteranceResume(): void {
    this.startMs = this.clockFn() - this.pauseOffsetMs;
    this.playing = true;
  }

  onUtteranceEnd(): void {
    this.playing = false;
    this.pauseOffsetMs = this.durationMs;
  }

  /**
   * Re-anchor the synthetic schedule to a measured word boundary. Browser TTS
   * reports boundary timestamps but no phonemes, so the opening estimate drifts
   * and the mouth falls out of step with the voice. Each measurement replaces
   * the clock offset, the remaining viseme schedule, and the total duration
   * that `getPlaybackTime`/`isPlaying` are judged against.
   */
  retarget(boundary: { startMs: number; visemes: VisemeEvent[]; durationMs: number }): void {
    if (this.playing) {
      this.startMs = this.clockFn() - boundary.startMs;
    } else {
      this.pauseOffsetMs = boundary.startMs;
    }
    this.visemes = boundary.visemes;
    this.durationMs = Math.max(boundary.startMs + 1, boundary.durationMs);
  }

  getPlaybackTime(): number {
    if (!this.playing) return this.pauseOffsetMs;
    const elapsed = this.clockFn() - this.startMs;
    return Math.max(0, Math.min(elapsed, this.durationMs));
  }

  getDuration(): number {
    return this.durationMs;
  }

  getWordAt(timeMs: number): TimedWord | null {
    return findActiveTimedItem(this.words, timeMs);
  }

  getVisemeAt(timeMs: number): VisemeEvent | null {
    return getActiveViseme(timeMs, this.visemes);
  }

  isPlaying(): boolean {
    return this.playing && this.getPlaybackTime() < this.durationMs;
  }
}

export interface WebAudioTimingOptions {
  id?: string;
  context: { currentTime: number; state: string };
  startTime: number;
  durationSeconds: number;
  words?: TimedWord[];
  visemes?: VisemeEvent[];
  isPlaying?: () => boolean;
}

export class WebAudioSpeechTimingSource implements SpeechTimingSource {
  readonly id: string;
  private context: WebAudioTimingOptions["context"];
  private startTime: number;
  private durationSeconds: number;
  private words: TimedWord[];
  private visemes: VisemeEvent[];
  private isPlayingFn?: () => boolean;

  constructor(options: WebAudioTimingOptions) {
    this.id = options.id ?? `webaudio-${Math.random().toString(36).slice(2, 8)}`;
    this.context = options.context;
    this.startTime = options.startTime;
    this.durationSeconds = Math.max(0, options.durationSeconds);
    this.words = options.words ?? [];
    this.visemes = options.visemes ?? [];
    this.isPlayingFn = options.isPlaying;
  }

  setTimeline(visemes: VisemeEvent[], words: TimedWord[] = []): void {
    this.visemes = visemes;
    this.words = words;
  }

  appendVisemes(visemes: VisemeEvent[]): void {
    this.visemes = this.visemes.concat(visemes);
  }

  setStartTime(startTime: number, durationSeconds?: number): void {
    this.startTime = startTime;
    if (typeof durationSeconds === "number") {
      this.durationSeconds = durationSeconds;
    }
  }

  getPlaybackTime(): number {
    if (this.context.state !== "running") return 0;
    const elapsed = this.context.currentTime - this.startTime;
    return Math.max(0, Math.min(elapsed * 1000, this.durationSeconds * 1000));
  }

  getDuration(): number {
    return this.durationSeconds * 1000;
  }

  getWordAt(timeMs: number): TimedWord | null {
    return findActiveTimedItem(this.words, timeMs);
  }

  getVisemeAt(timeMs: number): VisemeEvent | null {
    return getActiveViseme(timeMs, this.visemes);
  }

  isPlaying(): boolean {
    if (this.isPlayingFn) return this.isPlayingFn();
    if (this.context.state !== "running") return false;
    return (
      this.context.currentTime >= this.startTime &&
      this.context.currentTime <= this.startTime + this.durationSeconds
    );
  }
}

