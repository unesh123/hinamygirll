import { describe, expect, it } from "vitest";
import {
  ARKIT_BLENDSHAPES, ARKIT_COUNT, resolveArkitName, seededRng,
  ExpressionMixer, normalizeEmotions, EMOTION_NAMES, EMOTION_PROFILES,
  AudioLipSync, estimateVisemes, SILENCE_LEVEL,
  EyeSystem, nextBlinkInterval, sampleSaccade, eyeContextFor,
  BLINK_INTERVAL_MIN, BLINK_INTERVAL_MAX, SACCADE_MAX_AMPLITUDE, MICRO_SACCADE_MAX_AMPLITUDE,
  detectModelCapability, isGlbUrl,
  buildMorphBindings, applyArkitToMorphs, applyArkitToExpressions,
  BodyMotion, FaceEngine, emotionsFromAffect, resolveRenderQuality,
  type ArkitName,
} from "./index";

const SR = 48000;
const BINS = 512;

/** Synthetic magnitude spectrum with gaussian formant peaks over a quiet floor. */
function spectrum(peaks: [number, number][], floor = 0.05, height = 0.85): Float32Array {
  const s = new Float32Array(BINS).fill(floor);
  const binHz = SR / 2 / BINS;
  for (let i = 0; i < BINS; i++) {
    const hz = i * binHz;
    for (const [f, bw] of peaks) s[i] = Math.max(s[i], height * Math.exp(-0.5 * ((hz - f) / bw) ** 2));
  }
  return s;
}
const dominant = (v: Record<string, number>) => Object.entries(v).sort((a, b) => b[1] - a[1])[0][0];

describe("ARKit names", () => {
  it("has 52 unique shapes and resolves PerfectSync / short spellings", () => {
    expect(ARKIT_COUNT).toBe(52);
    expect(new Set(ARKIT_BLENDSHAPES).size).toBe(52);
    expect(resolveArkitName("EyeBlinkLeft")).toBe("eyeBlinkLeft");
    expect(resolveArkitName("mouthSmile_R")).toBe("mouthSmileRight");
    expect(resolveArkitName("mouthSmileL")).toBe("mouthSmileLeft");
    expect(resolveArkitName("mouthPucker")).toBe("mouthPucker");
    expect(resolveArkitName("Fcl_ALL_Joy")).toBeNull();
  });
});

describe("expression mixer", () => {
  it("normalizes weights to sum 1 with neutral absorbing the remainder", () => {
    const n = normalizeEmotions({ joy: 0.3, sorrow: 0.2 });
    expect(EMOTION_NAMES.reduce((s, k) => s + n[k], 0)).toBeCloseTo(1, 6);
    expect(n.neutral).toBeCloseTo(0.5, 6);
  });
  it("scales down over-budget blends and ignores negatives/NaN", () => {
    const n = normalizeEmotions({ joy: 2, anger: 2, fear: -1, shy: Number.NaN });
    expect(EMOTION_NAMES.reduce((s, k) => s + n[k], 0)).toBeCloseTo(1, 6);
    expect(n.joy).toBeCloseTo(0.5, 6);
    expect(n.fear).toBe(0);
    expect(n.neutral).toBeCloseTo(0, 6);
  });
  it("only references real ARKit names in profiles", () => {
    const valid = new Set<string>(ARKIT_BLENDSHAPES);
    for (const name of EMOTION_NAMES) for (const k of Object.keys(EMOTION_PROFILES[name].arkit)) expect(valid.has(k)).toBe(true);
  });
  it("drives both VRM presets and ARKit targets for joy", () => {
    const m = new ExpressionMixer({ rng: seededRng(1), microRate: 0 });
    m.setEmotions({ joy: 1 });
    let f = m.update(0.016, true);
    for (let i = 0; i < 120; i++) f = m.update(0.016, true);
    expect(f.vrm.happy).toBeGreaterThan(0.5);
    expect(f.arkit.mouthSmileLeft).toBeGreaterThan(0.3);
    expect(f.arkit.mouthSmileRight).toBeGreaterThan(0.3);
    expect(f.arkit.mouthFrownLeft).toBeLessThan(0.05);
  });
  it("keeps left/right asymmetry bounded", () => {
    const limit = 0.12;
    const m = new ExpressionMixer({ rng: seededRng(7), asymmetry: limit, microRate: 0 });
    m.setEmotions({ joy: 1 });
    let maxDiff = 0;
    let sawDiff = false;
    for (let i = 0; i < 1500; i++) {
      const f = m.update(0.016, true);
      const l = f.arkit.mouthSmileLeft;
      const r = f.arkit.mouthSmileRight;
      maxDiff = Math.max(maxDiff, Math.abs(l - r));
      if (Math.abs(l - r) > 0.005) sawDiff = true;
    }
    expect(sawDiff).toBe(true);
    // ±limit on each side of a ≤1 weight → difference ≤ 2·limit·weight(≈0.7)
    expect(maxDiff).toBeLessThanOrEqual(2 * limit * 0.7 + 1e-6);
  });
  it("attacks faster than it decays and settles back to rest", () => {
    const m = new ExpressionMixer({ rng: seededRng(3), asymmetry: 0, microRate: 0 });
    m.setEmotions({ surprise: 1 });
    let f = m.update(0.016, true);
    let attackFrames = 0;
    while (f.arkit.eyeWideLeft < 0.4 && attackFrames < 600) { f = m.update(0.016, true); attackFrames++; }
    for (let i = 0; i < 200; i++) f = m.update(0.016, true);
    const peak = f.arkit.eyeWideLeft;
    m.setEmotions({});
    let decayFrames = 0;
    while (f.arkit.eyeWideLeft > peak / 2 && decayFrames < 2000) { f = m.update(0.016, true); decayFrames++; }
    expect(decayFrames).toBeGreaterThan(attackFrames);
    for (let i = 0; i < 1000; i++) f = m.update(0.016, true);
    expect(f.arkit.eyeWideLeft).toBeLessThan(0.01);
    expect(f.vrm.neutral).toBeGreaterThan(0.9);
  });
  it("micro-expressions flicker in and out and stay small", () => {
    const m = new ExpressionMixer({ rng: seededRng(5), asymmetry: 0 });
    m.triggerMicro(0);
    expect(m.activeMicroCount).toBe(1);
    let peak = 0;
    let f = m.update(0.016, true);
    for (let i = 0; i < 100; i++) { f = m.update(0.016, true); peak = Math.max(peak, f.arkit.browInnerUp); }
    expect(peak).toBeGreaterThan(0.02);
    expect(peak).toBeLessThanOrEqual(0.22 * 0.6 + 1e-6);
    expect(m.activeMicroCount).toBe(0);
    expect(f.arkit.browInnerUp).toBeCloseTo(0, 5);
  });
  it("spawns flickers on its own unless suppressed", () => {
    const m = new ExpressionMixer({ rng: seededRng(11), microRate: 2 });
    let seen = 0;
    for (let i = 0; i < 600; i++) { m.update(0.016); seen = Math.max(seen, m.activeMicroCount); }
    expect(seen).toBeGreaterThan(0);
  });
  it("maps affect to emotions", () => {
    const e = emotionsFromAffect({ valence: 0.8, arousal: 0.7, playfulness: 0.5, warmth: 0.6, surprise: 0, thoughtfulness: 0, pout: 0, confidence: 0.5, drowsy: 0 });
    expect(e.joy).toBeGreaterThan(0.5);
    expect(e.sorrow).toBe(0);
    const s = emotionsFromAffect({ valence: -0.6, arousal: 0.2, playfulness: 0, warmth: 0, surprise: 0, thoughtfulness: 0, pout: 0, confidence: 0, drowsy: 0 });
    expect(s.sorrow).toBeGreaterThan(0.3);
  });
});

describe("audio lip-sync estimator", () => {
  it("returns a closed mouth for silence", () => {
    const e = estimateVisemes(new Float32Array(BINS), SR);
    expect(e.jawOpen).toBe(0);
    expect(Object.values(e.vowels).every((v) => v === 0)).toBe(true);
    const lip = new AudioLipSync();
    let f = lip.step(spectrum([[500, 80]], 0.01, 0.05), SR, 0.016);
    for (let i = 0; i < 30; i++) f = lip.step(new Float32Array(BINS), SR, 0.016);
    expect(f.active).toBe(false);
    expect(f.jawOpen).toBe(0);
    expect(f.mouthClose).toBeGreaterThan(0);
  });
  it("treats a flat quiet floor as silence", () => {
    expect(estimateVisemes(new Float32Array(BINS).fill(SILENCE_LEVEL * 0.8), SR).level).toBe(0);
  });
  it.each([
    ["aa", [[800, 90], [1250, 120]]],
    ["ee", [[350, 70], [2400, 150]]],
    ["ih", [[450, 70], [1900, 140]]],
    ["oh", [[520, 80], [900, 90]]],
    ["ou", [[350, 70], [800, 90]]],
  ] as const)("classifies a synthetic %s spectrum", (vowel, peaks) => {
    const floor = 0.22;
    const e = estimateVisemes(spectrum(peaks.map((p) => [...p] as [number, number]), floor), SR);
    expect(dominant(e.vowels)).toBe(vowel);
    expect(e.level).toBeGreaterThan(0);
  });
  it("opens the jaw wider for aa than ou and funnels lips for ou", () => {
    const aa = estimateVisemes(spectrum([[800, 90], [1250, 120]], 0.22), SR);
    const ou = estimateVisemes(spectrum([[350, 70], [800, 90]], 0.22), SR);
    expect(aa.jawOpen).toBeGreaterThan(ou.jawOpen);
    expect(ou.mouthFunnel).toBeGreaterThan(aa.mouthFunnel);
    expect(ou.mouthPucker).toBeGreaterThan(0);
  });
  it("smooths: ramps up on speech and releases to zero", () => {
    const lip = new AudioLipSync();
    const aa = spectrum([[800, 90], [1250, 120]], 0.22);
    const first = { ...lip.step(aa, SR, 0.016) };
    expect(first.aa).toBeGreaterThan(0);
    let f = first;
    for (let i = 0; i < 30; i++) f = lip.step(aa, SR, 0.016);
    expect(f.aa).toBeGreaterThan(first.aa);
    for (let i = 0; i < 60; i++) f = lip.step(new Float32Array(BINS), SR, 0.016);
    expect(f.aa).toBe(0);
    expect(f.active).toBe(false);
  });
  it("reads an AnalyserNode and falls back to closed with none", () => {
    const aa = spectrum([[800, 90], [1250, 120]], 0.22);
    const analyser = {
      frequencyBinCount: BINS,
      context: { sampleRate: SR },
      getByteFrequencyData(buf: Uint8Array) { for (let i = 0; i < BINS; i++) buf[i] = Math.round(aa[i] * 255); },
    } as unknown as AnalyserNode;
    const lip = new AudioLipSync();
    let f = lip.sample(analyser, 0.05);
    for (let i = 0; i < 10; i++) f = lip.sample(analyser, 0.05);
    expect(f.aa).toBeGreaterThan(0.2);
    for (let i = 0; i < 60; i++) f = lip.sample(null, 0.05);
    expect(f.active).toBe(false);
  });
});

describe("eye system", () => {
  it("keeps blink intervals inside bounds and scales with rate", () => {
    const rng = seededRng(42);
    for (let i = 0; i < 500; i++) {
      const v = nextBlinkInterval(rng, 1);
      expect(v).toBeGreaterThanOrEqual(BLINK_INTERVAL_MIN);
      expect(v).toBeLessThanOrEqual(BLINK_INTERVAL_MAX);
    }
    expect(nextBlinkInterval(() => 0.5, 2)).toBeLessThan(nextBlinkInterval(() => 0.5, 0.5));
  });
  it("bounds saccade and micro-saccade amplitude", () => {
    const rng = seededRng(9);
    for (let i = 0; i < 1000; i++) {
      const s = sampleSaccade(rng);
      expect(Math.hypot(s.x, s.y)).toBeLessThanOrEqual(SACCADE_MAX_AMPLITUDE + 1e-9);
      const m = sampleSaccade(rng, MICRO_SACCADE_MAX_AMPLITUDE);
      expect(Math.hypot(m.x, m.y)).toBeLessThanOrEqual(MICRO_SACCADE_MAX_AMPLITUDE + 1e-9);
    }
  });
  it("blinks within the expected cadence and fully closes", () => {
    const eyes = new EyeSystem(seededRng(21));
    let t = 0;
    let max = 0;
    let blinks = 0;
    let wasClosed = false;
    while (t < 60) {
      const f = eyes.update(0.016);
      t += 0.016;
      max = Math.max(max, f.blink);
      const closed = f.blink > 0.8;
      if (closed && !wasClosed) blinks++;
      wasClosed = closed;
    }
    expect(max).toBeGreaterThan(0.95);
    expect(blinks).toBeGreaterThanOrEqual(60 / (BLINK_INTERVAL_MAX + 1));
    expect(blinks).toBeLessThanOrEqual(60 / 0.8);
  });
  it("keeps gaze within eye travel and drives ARKit look channels", () => {
    const eyes = new EyeSystem(seededRng(4));
    let sawLook = false;
    for (let i = 0; i < 2000; i++) {
      const f = eyes.update(0.016);
      expect(Math.abs(f.gazeX)).toBeLessThanOrEqual(0.5);
      expect(Math.abs(f.gazeY)).toBeLessThanOrEqual(0.5);
      if ((f.arkit.eyeLookOutLeft ?? 0) + (f.arkit.eyeLookInLeft ?? 0) > 0.02) sawLook = true;
    }
    expect(sawLook).toBe(true);
  });
  it("looks away when thinking and lowers lids when gaze drops", () => {
    const ctx = eyeContextFor({ thinking: 0.8 }, { thinking: true });
    expect(ctx.gazeMode).toBe("away");
    expect(eyeContextFor({ sleepy: 0.9 }, {}).lidDroop).toBeGreaterThan(0.2);
    expect(eyeContextFor({ sleepy: 0.9 }, {}).blinkRate).toBeLessThan(1);
    const eyes = new EyeSystem(seededRng(2));
    let f = eyes.update(0.016, { gazeMode: "down", blinkRate: 0.5, saccadeScale: 0, lidDroop: 0 });
    for (let i = 0; i < 400; i++) f = eyes.update(0.016, { gazeMode: "down", blinkRate: 0.5, saccadeScale: 0, lidDroop: 0 });
    expect(f.gazeY).toBeLessThan(-0.05);
    expect(f.arkit.eyeLookDownLeft).toBeGreaterThan(0.05);
  });
  it("blink curve is closed at its midpoint and open at the ends", () => {
    expect(EyeSystem.blinkCurve(-1)).toBe(0);
    expect(EyeSystem.blinkCurve(0.08)).toBe(1);
    expect(EyeSystem.blinkCurve(1)).toBe(0);
  });
});

describe("capability detection", () => {
  const arkitNames = ARKIT_BLENDSHAPES.slice();
  it("detects VRM preset-only models", () => {
    const c = detectModelCapability({ isVrm: true, names: ["happy", "aa", "blink", "Fcl_ALL_Joy"] });
    expect(c.kind).toBe("vrm-preset");
    expect(c.hasArkit).toBe(false);
  });
  it("detects PerfectSync VRMs with Left/Right custom names", () => {
    const names = ["happy", ...arkitNames.map((n) => n[0].toUpperCase() + n.slice(1))];
    const c = detectModelCapability({ isVrm: true, names });
    expect(c.kind).toBe("vrm-perfectsync");
    expect(c.arkitCoverage).toBe(1);
    expect(c.arkit.get("jawOpen")).toBe("JawOpen");
  });
  it("detects ARKit GLBs and basic GLBs", () => {
    expect(detectModelCapability({ isVrm: false, names: arkitNames }).kind).toBe("glb-arkit");
    expect(detectModelCapability({ isVrm: false, names: ["Smile", "Blink"] }).kind).toBe("glb-basic");
  });
  it("needs core shapes, not just coverage", () => {
    const names = arkitNames.filter((n) => !n.startsWith("eyeBlink"));
    expect(detectModelCapability({ isVrm: false, names }).kind).toBe("glb-basic");
  });
  it("recognises glb/gltf urls", () => {
    expect(isGlbUrl("/models/face.glb")).toBe(true);
    expect(isGlbUrl("/models/face.GLB?x=1")).toBe(true);
    expect(isGlbUrl("/models/hina.vrm")).toBe(false);
  });
});

describe("morph and expression application", () => {
  it("writes ARKit weights into every mesh that owns the morph", () => {
    const head = { morphTargetDictionary: { jawOpen: 0, mouthSmile_L: 1, other: 2 }, morphTargetInfluences: [0, 0, 0.5] };
    const teeth = { morphTargetDictionary: { jawOpen: 0 }, morphTargetInfluences: [0] };
    const b = buildMorphBindings([head, teeth]);
    applyArkitToMorphs(b, { jawOpen: 0.6, mouthSmileLeft: 0.3 });
    expect(head.morphTargetInfluences).toEqual([0.6, 0.3, 0.5]);
    expect(teeth.morphTargetInfluences).toEqual([0.6]);
  });
  it("only writes expressions the VRM exposes", () => {
    const cap = detectModelCapability({ isVrm: true, names: ARKIT_BLENDSHAPES.map((n) => n.replace(/^./, (c) => c.toUpperCase())) });
    const written: Record<string, number> = {};
    applyArkitToExpressions({ setValue: (n, v) => { written[n] = v; } }, cap, { jawOpen: 0.4 } as Partial<Record<ArkitName, number>>, new Set<ArkitName>(["eyeBlinkLeft"]));
    expect(written.JawOpen).toBe(0.4);
    expect("EyeBlinkLeft" in written).toBe(false);
  });
});

describe("body motion", () => {
  it("breathes and bounds all offsets", () => {
    const b = new BodyMotion(seededRng(8));
    let min = 2;
    let max = 0;
    for (let i = 0; i < 1500; i++) {
      const p = b.update(0.016, { speaking: false, energy: 0 });
      min = Math.min(min, p.chestScale);
      max = Math.max(max, p.chestScale);
      expect(Math.abs(p.hipsX)).toBeLessThan(0.02);
      expect(Math.abs(p.headPitch)).toBeLessThan(0.05);
    }
    expect(max - min).toBeGreaterThan(0.005);
  });
  it("nods on loudness onsets and not when reduced-motion", () => {
    const run = (reducedMotion: boolean) => {
      const b = new BodyMotion(seededRng(8));
      let peak = 0;
      for (let i = 0; i < 100; i++) {
        const p = b.update(0.016, { speaking: true, energy: i < 5 ? 0 : 0.9, reducedMotion });
        peak = Math.max(peak, p.headPitch);
      }
      return peak;
    };
    expect(run(false)).toBeGreaterThan(0.03);
    expect(run(true)).toBeLessThan(0.02);
  });
});

describe("face engine", () => {
  const cap = detectModelCapability({ isVrm: false, names: ARKIT_BLENDSHAPES });
  it("merges emotion, eyes and audio lip-sync into one ARKit frame", () => {
    const aa = spectrum([[800, 90], [1250, 120]], 0.22);
    const analyser = {
      frequencyBinCount: BINS, context: { sampleRate: SR },
      getByteFrequencyData(buf: Uint8Array) { for (let i = 0; i < BINS; i++) buf[i] = Math.round(aa[i] * 255); },
    } as unknown as AnalyserNode;
    const engine = new FaceEngine({ capability: cap, rng: seededRng(1) });
    let f = engine.update(0.016, { speaking: true, analyser, emotions: { joy: 0.8 } });
    for (let i = 0; i < 60; i++) f = engine.update(0.016, { speaking: true, analyser });
    expect(f.audioLipSync).toBe(true);
    expect(f.arkit.jawOpen).toBeGreaterThan(0.2);
    expect(f.arkit.mouthSmileLeft).toBeGreaterThan(0.3);
    expect(engine.dominantEmotion).toBe("joy");
    for (const n of ARKIT_BLENDSHAPES) {
      expect(f.arkit[n]).toBeGreaterThanOrEqual(0);
      expect(f.arkit[n]).toBeLessThanOrEqual(1);
    }
  });
  it("defers to text visemes when there is no analyser", () => {
    const engine = new FaceEngine({ capability: cap, rng: seededRng(1) });
    const f = engine.update(0.016, { speaking: true, analyser: null });
    expect(f.audioLipSync).toBe(false);
  });
});

describe("render quality", () => {
  it("drops DPR, shadows and postprocessing on low power", () => {
    const q = resolveRenderQuality({ lowPower: true, devicePixelRatio: 3, realistic: true });
    expect(q.dpr).toBe(1);
    expect(q.shadows).toBe(false);
    expect(q.postprocessing).toBe(false);
  });
  it("detects low power from device hints and honours reduced motion", () => {
    expect(resolveRenderQuality({ deviceMemoryGb: 2 }).lowPower).toBe(true);
    const q = resolveRenderQuality({ devicePixelRatio: 3, reducedMotion: true, deviceMemoryGb: 16, hardwareConcurrency: 12 });
    expect(q.dpr).toBeLessThanOrEqual(1.25);
    expect(q.postprocessing).toBe(false);
    expect(resolveRenderQuality({ realistic: true, deviceMemoryGb: 16, hardwareConcurrency: 12, devicePixelRatio: 2 })).toMatchObject({ shadows: true, toneMapping: "agx", dpr: 2 });
  });
});
