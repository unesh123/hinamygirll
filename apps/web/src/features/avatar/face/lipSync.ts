import { clamp01 } from "./arkit";

export type Vowel = "aa" | "ih" | "ou" | "ee" | "oh";
export const VOWELS: readonly Vowel[] = ["aa", "ih", "ou", "ee", "oh"];

export interface LipSyncFrame {
  aa: number; ih: number; ou: number; ee: number; oh: number;
  jawOpen: number;
  mouthFunnel: number;
  mouthPucker: number;
  mouthSmile: number;
  mouthClose: number;
  /** 0..1 voiced loudness after gating. */
  level: number;
  /** True while audible speech is present (or the mouth is still releasing). */
  active: boolean;
}

/** (F1, F2) centres in Hz for the five Japanese/VRM vowels. */
export const VOWEL_FORMANTS: Record<Vowel, [number, number]> = {
  aa: [800, 1250],
  ee: [350, 2400],
  ih: [450, 1900],
  oh: [520, 900],
  ou: [350, 800],
};
const SIGMA_F1 = 140;
const SIGMA_F2 = 400;

/** Jaw contribution per vowel (open vowels open the jaw most). */
const JAW_FACTOR: Record<Vowel, number> = { aa: 1, oh: 0.75, ou: 0.35, ih: 0.4, ee: 0.3 };

/** Normalised level (0..1 of the analyser's byte range) below which we call it silence. */
export const SILENCE_LEVEL = 0.18;
const FULL_LEVEL = 0.6;

export interface SpectrumEstimate {
  vowels: Record<Vowel, number>;
  jawOpen: number;
  mouthFunnel: number;
  mouthPucker: number;
  mouthSmile: number;
  level: number;
  f1: number;
  f2: number;
  fricative: number;
}

const ZERO_VOWELS = (): Record<Vowel, number> => ({ aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });

function bandMean(spec: ArrayLike<number>, binHz: number, lo: number, hi: number): number {
  const a = Math.max(0, Math.floor(lo / binHz));
  const b = Math.min(spec.length - 1, Math.ceil(hi / binHz));
  if (b < a) return 0;
  let s = 0;
  for (let i = a; i <= b; i++) s += spec[i];
  return s / (b - a + 1);
}

/** Strongest peak in [lo,hi], ignoring bins within `exclude` Hz of `around` (pass around<0 to disable). */
function peakHz(smooth: Float32Array, binHz: number, lo: number, hi: number, around = -1, exclude = 0): number {
  const a = Math.max(1, Math.floor(lo / binHz));
  const b = Math.min(smooth.length - 2, Math.ceil(hi / binHz));
  let best = -1;
  for (let i = a; i <= b; i++) {
    if (around >= 0 && Math.abs(i * binHz - around) < exclude) continue;
    if (best < 0 || smooth[i] > smooth[best]) best = i;
  }
  return best < 0 ? 0 : best * binHz;
}

/**
 * Estimate mouth shape from one frequency-domain frame.
 * @param spectrum magnitudes normalised to 0..1 (analyser bytes / 255), bin 0 = DC
 * @param sampleRate audio context sample rate (Hz)
 *
 * Heuristic: the strongest peak in 200–1000 Hz approximates F1 (jaw height) and the
 * strongest peak above it in 900–3200 Hz approximates F2 (tongue/lip position). Each vowel
 * gets a Gaussian membership in (F1,F2) space; the result is scaled by voiced loudness.
 */
export function estimateVisemes(spectrum: ArrayLike<number>, sampleRate: number): SpectrumEstimate {
  const n = spectrum.length;
  const binHz = sampleRate / 2 / n;
  const vowels = ZERO_VOWELS();
  const empty: SpectrumEstimate = {
    vowels, jawOpen: 0, mouthFunnel: 0, mouthPucker: 0, mouthSmile: 0, level: 0, f1: 0, f2: 0, fricative: 0,
  };
  if (n < 8 || !(sampleRate > 0)) return empty;

  const voiced = bandMean(spectrum, binHz, 80, 4000);
  if (voiced < SILENCE_LEVEL) return empty;
  const level = clamp01((voiced - SILENCE_LEVEL) / (FULL_LEVEL - SILENCE_LEVEL));

  const smooth = new Float32Array(n);
  for (let i = 1; i < n - 1; i++) smooth[i] = (spectrum[i - 1] + 2 * spectrum[i] + spectrum[i + 1]) / 4;

  // Strongest peak = F1; strongest peak at least 300 Hz away = F2. Rounded vowels put F2 below 1 kHz.
  const p1 = peakHz(smooth, binHz, 200, 3200);
  const p2 = peakHz(smooth, binHz, 200, 3200, p1, 300);
  const f1 = Math.min(p1, p2 || p1);
  const f2 = Math.max(p1, p2);

  const high = bandMean(spectrum, binHz, 4500, 9000);
  const fricative = clamp01((high - voiced) / 0.25 + 0.1) * (high > SILENCE_LEVEL ? 1 : 0);

  let total = 0;
  for (const v of VOWELS) {
    const [c1, c2] = VOWEL_FORMANTS[v];
    const d = ((f1 - c1) / SIGMA_F1) ** 2 + ((f2 - c2) / SIGMA_F2) ** 2;
    vowels[v] = Math.exp(-0.5 * d);
    total += vowels[v];
  }
  if (total < 1e-6) return { ...empty, level, f1, f2 };
  let jaw = 0;
  for (const v of VOWELS) {
    vowels[v] = (vowels[v] / total) * level;
    jaw += vowels[v] * JAW_FACTOR[v];
  }
  // Sibilants/fricatives: teeth nearly together, lips spread.
  const spread = fricative * 0.5 * level;
  vowels.ee = clamp01(vowels.ee + spread);
  jaw *= 1 - fricative * 0.5;

  return {
    vowels,
    jawOpen: clamp01(jaw * 1.15),
    mouthFunnel: clamp01(vowels.ou * 0.8 + vowels.oh * 0.35),
    mouthPucker: clamp01(vowels.ou * 0.7),
    mouthSmile: clamp01(vowels.ee * 0.6 + vowels.ih * 0.2),
    level,
    f1,
    f2,
    fricative,
  };
}

export interface AudioLipSyncOptions {
  attackRate?: number;
  releaseRate?: number;
  /** Mouth-closed pressure at rest, 0..1. */
  restClose?: number;
}

const zeroFrame = (): LipSyncFrame => ({
  aa: 0, ih: 0, ou: 0, ee: 0, oh: 0, jawOpen: 0, mouthFunnel: 0, mouthPucker: 0,
  mouthSmile: 0, mouthClose: 0, level: 0, active: false,
});

/** Smooths per-frame estimates; fed either raw spectra (`step`) or an AnalyserNode (`sample`). */
export class AudioLipSync {
  private frame = zeroFrame();
  private attack: number;
  private release: number;
  private restClose: number;
  private buf: Uint8Array | null = null;
  private norm: Float32Array | null = null;

  constructor(opts: AudioLipSyncOptions = {}) {
    this.attack = opts.attackRate ?? 28;
    this.release = opts.releaseRate ?? 16;
    this.restClose = opts.restClose ?? 0.2;
  }

  reset(): void { this.frame = zeroFrame(); }

  step(spectrum: ArrayLike<number> | null, sampleRate: number, dt: number): LipSyncFrame {
    dt = Math.max(0, Math.min(dt, 0.1));
    const est = spectrum ? estimateVisemes(spectrum, sampleRate) : null;
    const f = this.frame;
    const ease = (cur: number, tgt: number) =>
      cur + (tgt - cur) * (1 - Math.exp(-dt * (tgt > cur ? this.attack : this.release)));
    const t = est ?? { vowels: ZERO_VOWELS(), jawOpen: 0, mouthFunnel: 0, mouthPucker: 0, mouthSmile: 0, level: 0 };
    for (const v of VOWELS) f[v] = ease(f[v], t.vowels[v]);
    f.jawOpen = ease(f.jawOpen, t.jawOpen);
    f.mouthFunnel = ease(f.mouthFunnel, t.mouthFunnel);
    f.mouthPucker = ease(f.mouthPucker, t.mouthPucker);
    f.mouthSmile = ease(f.mouthSmile, t.mouthSmile);
    f.level = ease(f.level, t.level);
    // Lips press together as the jaw closes; fully open vowels release them.
    f.mouthClose = ease(f.mouthClose, this.restClose * (1 - clamp01(t.jawOpen * 3)) * (1 - clamp01(f.jawOpen * 3)));
    f.active = f.level > 0.02 || f.jawOpen > 0.02;
    if (!f.active) {
      for (const v of VOWELS) f[v] = 0;
      f.jawOpen = f.mouthFunnel = f.mouthPucker = f.mouthSmile = 0;
    }
    return f;
  }

  /** Read the analyser (any fftSize) and advance smoothing. Pass null when no audio node exists. */
  sample(analyser: AnalyserNode | null, dt: number): LipSyncFrame {
    if (!analyser) return this.step(null, 48000, dt);
    const bins = analyser.frequencyBinCount;
    if (!this.buf || this.buf.length !== bins) {
      this.buf = new Uint8Array(bins);
      this.norm = new Float32Array(bins);
    }
    analyser.getByteFrequencyData(this.buf as Uint8Array<ArrayBuffer>);
    const norm = this.norm!;
    for (let i = 0; i < bins; i++) norm[i] = this.buf[i] / 255;
    return this.step(norm, analyser.context.sampleRate, dt);
  }
}

/** Text-timed fallback: turn one active viseme into the same ARKit-ready shape the audio path produces. */
export function visemeToLipFrame(
  mouth: Vowel | "closed",
  weight: number,
  out: Pick<LipSyncFrame, "jawOpen" | "mouthFunnel" | "mouthPucker" | "mouthSmile">,
): void {
  const w = clamp01(weight);
  out.jawOpen = out.mouthFunnel = out.mouthPucker = out.mouthSmile = 0;
  switch (mouth) {
    case "aa": out.jawOpen = 0.75 * w; break;
    case "oh": out.jawOpen = 0.5 * w; out.mouthFunnel = 0.55 * w; break;
    case "ou": out.jawOpen = 0.22 * w; out.mouthFunnel = 0.4 * w; out.mouthPucker = 0.6 * w; break;
    case "ee": out.jawOpen = 0.2 * w; out.mouthSmile = 0.55 * w; break;
    case "ih": out.jawOpen = 0.28 * w; out.mouthSmile = 0.25 * w; break;
    default: break;
  }
}
