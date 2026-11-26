export class AudioManager {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private drivetrainOsc: OscillatorNode | null = null;
  private drivetrainGain: GainNode | null = null;
  private ambientOsc: OscillatorNode | null = null;
  private ambientGain: GainNode | null = null;
  private volume = 0.55;
  private muted = false;
  private unlocked = false;
  private lastBrakeMs = 0;

  unlock(): void {
    if (this.unlocked && this.ctx) {
      if (this.ctx.state === "suspended") {
        void this.ctx.resume().catch(() => {});
      }
      return;
    }
    if (typeof window === "undefined") return;
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;

    try {
      const ctx = new AudioCtx();
      const master = ctx.createGain();
      master.gain.value = this.muted ? 0 : this.volume;
      master.connect(ctx.destination);

      // Subtle futuristic hub-drive bicycle hum modulated cleanly by wheel RPM
      const driveOsc = ctx.createOscillator();
      const driveFilter = ctx.createBiquadFilter();
      const driveGain = ctx.createGain();
      driveOsc.type = "triangle";
      driveOsc.frequency.value = 55;
      driveFilter.type = "lowpass";
      driveFilter.frequency.value = 320;
      driveGain.gain.value = 0;
      driveOsc.connect(driveFilter);
      driveFilter.connect(driveGain);
      driveGain.connect(master);
      driveOsc.start();

      // Low-level nocturnal urban synth pad
      const ambOsc = ctx.createOscillator();
      const ambFilter = ctx.createBiquadFilter();
      const ambGain = ctx.createGain();
      ambOsc.type = "sine";
      ambOsc.frequency.value = 73.42; // D2
      ambFilter.type = "lowpass";
      ambFilter.frequency.value = 210;
      ambGain.gain.value = 0.03;
      ambOsc.connect(ambFilter);
      ambFilter.connect(ambGain);
      ambGain.connect(master);
      ambOsc.start();

      this.ctx = ctx;
      this.masterGain = master;
      this.drivetrainOsc = driveOsc;
      this.drivetrainGain = driveGain;
      this.ambientOsc = ambOsc;
      this.ambientGain = ambGain;
      this.unlocked = true;
    } catch {
      // ignore sandboxed audio restrictions
    }
  }

  destroy(): void {
    try {
      this.drivetrainOsc?.stop();
      this.ambientOsc?.stop();
      void this.ctx?.close();
    } catch {
      // ignore teardown errors
    }
    this.ctx = null;
    this.unlocked = false;
  }

  setVolumeAndMute(volume: number, muted: boolean): void {
    this.volume = Math.max(0, Math.min(1, volume));
    this.muted = muted;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setTargetAtTime(muted ? 0 : this.volume, this.ctx.currentTime, 0.04);
    }
  }

  updateContinuum(speedPx: number, boosting: boolean, grounded: boolean, brakingHard: boolean, playing: boolean): void {
    if (!this.ctx || !this.drivetrainOsc || !this.drivetrainGain || !this.ambientGain) return;
    const now = this.ctx.currentTime;
    if (!playing || this.muted) {
      this.drivetrainGain.gain.setTargetAtTime(0, now, 0.05);
      this.ambientGain.gain.setTargetAtTime(playing && !this.muted ? 0.03 : 0, now, 0.12);
      return;
    }
    const speedRatio = Math.min(1, Math.abs(speedPx) / 700);
    const freq = 52 + speedRatio * (boosting ? 175 : 108);
    const gain = grounded ? 0.015 + speedRatio * (boosting ? 0.095 : 0.055) : 0.01 + speedRatio * 0.025;
    this.drivetrainOsc.frequency.setTargetAtTime(freq, now, 0.05);
    this.drivetrainGain.gain.setTargetAtTime(gain, now, 0.05);
    this.ambientGain.gain.setTargetAtTime(0.032, now, 0.15);

    if (brakingHard) {
      const perfNow = performance.now();
      if (perfNow - this.lastBrakeMs > 180) {
        this.lastBrakeMs = perfNow;
        this.playTone(980, 520, 0.09, "sawtooth", 0.04);
      }
    }
  }

  private playTone(
    startHz: number,
    endHz: number,
    durationSec: number,
    type: OscillatorType,
    level: number,
  ): void {
    if (!this.ctx || !this.masterGain || this.muted) return;
    const t0 = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(startHz, t0);
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, endHz), t0 + durationSec);
    g.gain.setValueAtTime(level, t0);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + durationSec);
    osc.connect(g);
    g.connect(this.masterGain);
    osc.start(t0);
    osc.stop(t0 + durationSec + 0.02);
  }

  playJump(): void {
    this.playTone(190, 410, 0.14, "triangle", 0.11);
  }

  playLanding(impulse: number): void {
    const strength = Math.min(0.18, 0.04 + (impulse / 750) * 0.14);
    this.playTone(125, 42, 0.13, "sine", strength);
  }

  playCollect(isStar: boolean): void {
    if (isStar) {
      this.playTone(660, 1180, 0.18, "sine", 0.1);
    } else {
      this.playTone(520, 880, 0.12, "triangle", 0.08);
    }
  }

  playSmash(): void {
    this.playTone(170, 52, 0.16, "sawtooth", 0.11);
  }

  playCheckpoint(): void {
    this.playTone(440, 880, 0.22, "sine", 0.12);
  }

  playCrash(): void {
    this.playTone(210, 38, 0.32, "sawtooth", 0.16);
  }

  playFinish(): void {
    this.playTone(523.25, 1046.5, 0.35, "triangle", 0.15);
  }
}
