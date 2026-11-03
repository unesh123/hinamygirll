import { describe, expect, it } from "vitest";
import {
  PerformanceDirector,
  EmotionRuntime,
  BlinkRuntime,
  GazeRuntime,
  PostureRuntime,
} from "./performanceSubstrate";
import { SyntheticSpeechTimingSource } from "../audio/speechTimingSource";

describe("Avatar Performance Substrate", () => {
  it("advances fallback visemes using the speech playback clock", () => {
    const director = new PerformanceDirector();
    director.setState("SPEAKING");
    const fallbackVisemes = [
      { timeMs: 0, durationMs: 100, mouth: "aa" as const, weight: 1 },
      { timeMs: 100, durationMs: 300, mouth: "ou" as const, weight: 1 },
    ];
    const frame = director.update(0.1, 20, { fallbackVisemes, playbackTimeMs: 180 });
    expect(frame.lipSync.ou).toBeGreaterThan(0.8);
    expect(frame.lipSync.aa).toBe(0);
    const silence = director.update(0.1, 20.4, { fallbackVisemes, playbackTimeMs: 600 });
    expect(silence.lipSync.ou).toBeLessThan(frame.lipSync.ou);
  });

  it("uses calibrated playback time when a timing source is present", () => {
    const director = new PerformanceDirector();
    director.setState("SPEAKING");
    const timing = new SyntheticSpeechTimingSource({
      durationMs: 1000,
      visemes: [
        { timeMs: 0, durationMs: 100, mouth: "aa", weight: 1 },
        { timeMs: 100, durationMs: 300, mouth: "ou", weight: 1 },
      ],
    });
    const frame = director.update(0.1, 20, { timingSource: timing, playbackTimeMs: 180 });
    expect(frame.lipSync.ou).toBeGreaterThan(0.8);
    expect(frame.lipSync.aa).toBe(0);
  });

  it("EmotionRuntime tracks emotion and clamps intensity", () => {
    const runtime = new EmotionRuntime();
    expect(runtime.getEmotion()).toBe("neutral");
    runtime.setEmotion("happy", 0.85);
    expect(runtime.getEmotion()).toBe("happy");
    expect(runtime.getIntensity()).toBe(0.85);
    runtime.setEmotion("excited", 1.5);
    expect(runtime.getIntensity()).toBe(1.0);
  });

  it("GazeRuntime adjusts gaze vector according to PerformanceState", () => {
    const runtime = new GazeRuntime();
    // Listening looks directly at user with forward depth
    const listening = runtime.update("LISTENING", "neutral", 1.0);
    expect(listening.z).toBeGreaterThan(1.2);

    // Thinking averts gaze sideways/upwards
    const thinking = runtime.update("THINKING", "thinking", 1.0);
    expect(Math.abs(thinking.x)).toBeGreaterThan(0.2);

    // Working with codeMode looks toward code side
    const working = runtime.update("WORKING", "neutral", 1.0, true);
    expect(working.x).toBeGreaterThan(0.3);
  });

  it("BlinkRuntime ramps an eased blink instead of snapping shut", () => {
    const runtime = new BlinkRuntime();
    runtime.reset(0);
    // Before the scheduled blink time the lids stay open.
    expect(runtime.update(0.016, 0)).toBe(0);

    const frames: number[] = [];
    for (let i = 0; i < 24; i++) {
      frames.push(runtime.update(0.016, 6.0 + i * 0.016));
    }
    // Closure ramps past halfway and returns to open by the end of the blink.
    expect(Math.max(...frames)).toBeGreaterThanOrEqual(0.5);
    expect(frames[frames.length - 1]).toBe(0);
    expect(runtime.update(0.016, 7.0, true)).toBe(0);
  });

  it("PostureRuntime updates head tilt and arm gestures", () => {
    const runtime = new PostureRuntime();
    const nod = runtime.update("IDLE", "small_nod", 1.0);
    expect(nod.head.x).not.toBe(0);

    const wave = runtime.update("IDLE", "wave", 1.0, 1.0, true);
    expect(wave.arms.rightArm.x).toBe(-0.6);
  });

  it("PerformanceDirector orchestrates state transitions and resets lipsync on INTERRUPTED", () => {
    const director = new PerformanceDirector();
    expect(director.getState()).toBe("IDLE");

    const timing = new SyntheticSpeechTimingSource({
      durationMs: 1000,
      visemes: [{ timeMs: 0, durationMs: 500, mouth: "aa", weight: 0.9 }],
    });
    timing.start();

    director.setState("SPEAKING");
    director.update(0.016, 1.0, { timingSource: timing });
    director.update(0.016, 1.05, { timingSource: timing });
    expect(director.lipSyncRuntime.getCurrentWeights().aa).toBeGreaterThan(0.1);

    // Interruption
    director.setState("INTERRUPTED");
    expect(director.getState()).toBe("INTERRUPTED");
    expect(director.lipSyncRuntime.getCurrentWeights().aa).toBe(0);
  });
});
