/** Device-local timing samples. Never stores messages, audio, keys, or account data. */
export class RuntimeMeasurements {
  private frames = new Float32Array(600);
  private count = 0;
  private cursor = 0;
  private lastFrameAt = 0;
  private turn = 0;
  private turnAt = 0;
  private spoken = false;
  private onset: number | null = null;
  private provider: string | null = null;
  private synthesis: number | null = null;
  recordFrame(seconds: number, now = performance.now()) {
    if (!Number.isFinite(seconds) || seconds <= 0 || seconds > 5) return;
    this.frames[this.cursor] = seconds * 1000;
    this.cursor = (this.cursor + 1) % this.frames.length;
    this.count = Math.min(this.count + 1, this.frames.length);
    this.lastFrameAt = now;
  }
  beginTurn(now = performance.now()) {this.turnAt = now; this.spoken = false; this.onset = null; this.turn += 1; return this.turn;}
  speechStarted(turn: number, provider: string, now = performance.now()) {
    if (turn !== this.turn || this.spoken) return;
    this.onset = Math.max(0, now - this.turnAt); this.provider = provider; this.spoken = true;
  }
  synthesized(milliseconds: number) {if (Number.isFinite(milliseconds) && milliseconds >= 0) this.synthesis = milliseconds;}
  snapshot(now = performance.now()) {
    const samples = Array.from(this.frames.slice(0, this.count)).sort((a,b) => a-b);
    const active = this.count >= 30 && now - this.lastFrameAt < 3000;
    return {frameSamples: this.count,
      fps: active ? 1000 / (samples.reduce((sum,n) => sum+n, 0) / this.count) : null,
      frameP95Ms: active ? samples[Math.min(samples.length-1, Math.ceil(samples.length*.95)-1)] : null,
      speechOnsetMs: this.onset, synthesisMs: this.synthesis, speechProvider: this.provider};
  }
}
export const runtimeMeasurements = new RuntimeMeasurements();
