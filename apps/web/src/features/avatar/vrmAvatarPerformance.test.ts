import { describe, expect, it } from "vitest";
import { PerformanceDirector } from "./performanceSubstrate";
import { WebAudioSpeechTimingSource, BrowserSpeechTimingSource } from "../audio/speechTimingSource";

describe("PerformanceDirector with Speech Timing Sources", () => {
  it("drives real-time mouth shapes when WebAudio timing is actively playing", () => {
    const director = new PerformanceDirector();
    director.setState("SPEAKING");

    const mockContext = { currentTime: 0.1, state: "running" };
    const timing = new WebAudioSpeechTimingSource({
      context: mockContext,
      startTime: 0,
      durationSeconds: 1.0,
      visemes: [
        { mouth: "aa", weight: 0.8, timeMs: 50, durationMs: 200 },
        { mouth: "ou", weight: 0.9, timeMs: 260, durationMs: 240 },
      ],
      isPlaying: () => true,
    });

    // Frame 1: at 100ms
    const out1 = director.update(0.016, 0.1, {
      timingSource: timing,
      jawEnergy: 0.5,
    });

    expect(out1.state).toBe("SPEAKING");
    expect(out1.lipSync.aa).toBeGreaterThan(0);
    expect(out1.lipSync.jawOpen).toBeGreaterThan(0);
    expect(out1.expressions.aa).toBeGreaterThan(0);

    // Frame 2: advance audio time to 300ms
    mockContext.currentTime = 0.3;
    const out2 = director.update(0.016, 0.3, {
      timingSource: timing,
      jawEnergy: 0.6,
    });

    expect(out2.lipSync.ou).toBeGreaterThan(0);
  });

  it("handles interruption state by resetting lip-sync immediately", () => {
    const director = new PerformanceDirector();
    director.setState("SPEAKING");

    const timing = new BrowserSpeechTimingSource({
      durationMs: 2000,
      visemes: [{ mouth: "aa", weight: 1.0, timeMs: 0, durationMs: 1000 }],
    });
    timing.onUtteranceStart();

    const outSpeaking = director.update(0.016, 0.1, { timingSource: timing, jawEnergy: 0.7 });
    expect(outSpeaking.lipSync.aa).toBeGreaterThan(0);

    // Interrupt turn
    director.setState("INTERRUPTED");
    expect(director.getState()).toBe("INTERRUPTED");

    const outInterrupted = director.update(0.016, 0.2, { timingSource: timing, jawEnergy: 0 });
    expect(outInterrupted.lipSync.aa).toBe(0);
    expect(outInterrupted.lipSync.jawOpen).toBe(0);
  });

  it("produces valid gaze and posture targets without NaN under all states", () => {
    const director = new PerformanceDirector();
    const states = ["IDLE", "LISTENING", "THINKING", "WORKING", "SPEAKING"] as const;

    for (const st of states) {
      director.setState(st);
      director.emotionRuntime.setEmotion("happy", 0.8);
      const out = director.update(0.016, 1.5, { gesture: "wave" });

      expect(Number.isFinite(out.gaze.x)).toBe(true);
      expect(Number.isFinite(out.gaze.y)).toBe(true);
      expect(Number.isFinite(out.gaze.z)).toBe(true);
      expect(Number.isFinite(out.head.x)).toBe(true);
      expect(Number.isFinite(out.head.y)).toBe(true);
      expect(Number.isFinite(out.head.z)).toBe(true);
      expect(out.gaze.confidence).toBeGreaterThan(0);
    }
  });
});
