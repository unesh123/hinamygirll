export type LatencyMilestone =
  | "live_session_started"
  | "microphone_ready"
  | "speech_started"
  | "first_stt_partial"
  | "speech_ended"
  | "turn_committed"
  | "stt_final"
  | "llm_request_started"
  | "first_text_delta"
  | "first_stable_phrase"
  | "tts_request_started"
  | "first_audio_chunk"
  | "playback_started"
  | "final_text"
  | "final_audio"
  | "turn_completed"
  | "interruption_detected"
  | "playback_stopped"
  | "server_cancel_acknowledged";

/**
 * Monotonic latency instrumentation. Never invents missing milestones.
 */
export class LatencyClock {
  private marks = new Map<LatencyMilestone, number>();
  private readonly now: () => number;

  constructor(now: () => number = () => performance.now()) {
    this.now = now;
  }

  reset(): void {
    this.marks.clear();
  }

  mark(name: LatencyMilestone): void {
    if (!this.marks.has(name)) this.marks.set(name, this.now());
  }

  get(name: LatencyMilestone): number | undefined {
    return this.marks.get(name);
  }

  delta(from: LatencyMilestone, to: LatencyMilestone): number | undefined {
    const a = this.marks.get(from);
    const b = this.marks.get(to);
    if (a === undefined || b === undefined) return undefined;
    return Math.round(b - a);
  }

  snapshot(): Partial<Record<LatencyMilestone, number>> {
    return Object.fromEntries(this.marks.entries()) as Partial<
      Record<LatencyMilestone, number>
    >;
  }
}
