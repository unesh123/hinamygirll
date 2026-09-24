import { describe, expect, it } from "vitest";
import { LipSyncRuntime } from "./lipSyncRuntime";
import { SyntheticSpeechTimingSource } from "../audio/speechTimingSource";

describe("LipSyncRuntime", () => {
  it("initializes with zeroed blendshapes in rest position", () => {
    const runtime = new LipSyncRuntime();
    const weights = runtime.getCurrentWeights();
    expect(weights.aa).toBe(0);
    expect(weights.ih).toBe(0);
    expect(weights.ou).toBe(0);
    expect(weights.ee).toBe(0);
    expect(weights.oh).toBe(0);
    expect(weights.jawOpen).toBe(0);
  });

  it("applies smooth attack rather than instantaneous pop to 1.0", () => {
    const runtime = new LipSyncRuntime({ attackTimeMs: 50, releaseTimeMs: 80 });
    const timing = new SyntheticSpeechTimingSource({
      durationMs: 1000,
      visemes: [{ timeMs: 0, durationMs: 500, mouth: "aa", weight: 1.0 }],
    });
    timing.start();

    // After a single 16ms frame (60fps)
    const frame1 = runtime.update(0.016, timing);
    // Should have started rising smoothly, definitely not 0, and definitely not 1.0
    expect(frame1.aa).toBeGreaterThan(0.1);
    expect(frame1.aa).toBeLessThan(0.5);
    expect(frame1.jawOpen).toBeGreaterThan(0.05);

    // After several frames (approx 80ms total)
    let weights = frame1;
    for (let i = 0; i < 4; i++) {
      weights = runtime.update(0.016, timing);
    }
    expect(weights.aa).toBeGreaterThan(0.7);
  });

  it("applies smooth release when sound ends without snapping to zero", () => {
    const runtime = new LipSyncRuntime({ attackTimeMs: 40, releaseTimeMs: 80 });
    const timing = new SyntheticSpeechTimingSource({
      durationMs: 300,
      visemes: [{ timeMs: 0, durationMs: 200, mouth: "ee", weight: 0.9 }],
    });
    timing.start();

    // Run into active speaking zone
    for (let i = 0; i < 10; i++) {
      runtime.update(0.016, timing, { customTimeMs: 100 });
    }
    const peak = runtime.getCurrentWeights().ee;
    expect(peak).toBeGreaterThan(0.7);

    // Now silence starts at 250ms
    const releaseFrame1 = runtime.update(0.016, timing, { customTimeMs: 250 });
    // Should still have non-zero mouth opening during decay
    expect(releaseFrame1.ee).toBeGreaterThan(0.3);
    expect(releaseFrame1.ee).toBeLessThan(peak);

    // After 240ms of silence (3 * releaseTimeMs), decays close to 0
    for (let i = 0; i < 15; i++) {
      runtime.update(0.016, timing, { customTimeMs: 250 + i * 16 });
    }
    expect(runtime.getCurrentWeights().ee).toBeLessThan(0.05);
  });

  it("anticipates approaching vowel via lookahead window", () => {
    const runtime = new LipSyncRuntime({ lookaheadMs: 50 });
    const timing = new SyntheticSpeechTimingSource({
      durationMs: 1000,
      visemes: [
        { timeMs: 0, durationMs: 100, mouth: "closed", weight: 0 },
        { timeMs: 100, durationMs: 300, mouth: "ou", weight: 0.9 },
      ],
    });
    timing.start();

    // At 60ms, current viseme is still "closed", but 60ms + 50ms lookahead = 110ms is "ou"
    const frameAt60ms = runtime.update(0.016, timing, { customTimeMs: 60 });
    // Lookahead coarticulation starts warming up "ou" before 100ms
    expect(frameAt60ms.ou).toBeGreaterThan(0.05);
  });

  it("computes auxiliary blendshapes correctly for vowels", () => {
    const runtime = new LipSyncRuntime();
    const timing = new SyntheticSpeechTimingSource({
      durationMs: 1000,
      visemes: [{ timeMs: 0, durationMs: 500, mouth: "ou", weight: 0.9 }],
    });
    timing.start();

    for (let i = 0; i < 10; i++) {
      runtime.update(0.016, timing, { customTimeMs: 50 });
    }
    const weights = runtime.getCurrentWeights();
    // For 'ou', mouthPucker and mouthFunnel should be engaged
    expect(weights.mouthPucker).toBeGreaterThan(0.3);
    expect(weights.mouthFunnel).toBeGreaterThan(0.2);
  });
});
