import { describe, expect, it } from "vitest";
import {
  buildVrmExpressionWeights,
  VRM_EXPRESSION_KEYS,
  type VrmExpressionInput,
  type VrmExpressionWeights,
} from "./vrmExpressionMap";
import { textToVisemeEvents, getActiveViseme } from "../audio/textToViseme";

describe("1,000-Cycle VRM Lip Sync & Syllable Modulation Benchmark", () => {
  it("executes 1,000 consecutive speech frames with bounded, non-glitching visemes", () => {
    const speechPhonemes = ["aa", "ih", "ou", "oh", "ee", "closed"];
    const emotions = ["neutral", "happy", "excited", "playful", "surprised", "shy"];
    let previousJaw = 0;

    for (let cycle = 0; cycle < 1000; cycle++) {
      // Simulate real-time audio time progressing at 60 FPS (~16.6ms per frame)
      const timeSec = cycle * 0.0166;
      const elapsedMs = cycle * 16.6;

      // 4.9 Hz natural syllable envelope with micro-variations
      const syllableOsc = 0.42 + 0.34 * Math.sin(timeSec * 2 * Math.PI * 4.9) + 0.14 * Math.sin(timeSec * 2 * Math.PI * 8.4);
      const rawTarget = Math.max(0, Math.min(1.0, syllableOsc));
      // Exponential moving average smoothing like in useAudioPlayback
      const jawEnergy = previousJaw + (rawTarget - previousJaw) * 0.4;
      previousJaw = jawEnergy;

      const emotion = emotions[cycle % emotions.length];
      const isSpeaking = cycle % 30 !== 0; // Brief 1-frame micro-pauses between phrases

      const input: VrmExpressionInput = {
        emotion,
        intensity: 0.5 + 0.5 * Math.sin(cycle * 0.05),
        jawEnergy: isSpeaking ? jawEnergy : 0,
        blinking: cycle % 180 >= 174, // Blink every ~3 seconds for 6 frames
        speaking: isSpeaking,
        reducedMotion: false,
      };

      const weights = buildVrmExpressionWeights(input);

      // Verify every single expression key is within [0.0, 1.0] and never NaN
      for (const key of VRM_EXPRESSION_KEYS) {
        const val = weights[key];
        expect(Number.isFinite(val)).toBe(true);
        expect(val).toBeGreaterThanOrEqual(0);
        expect(val).toBeLessThanOrEqual(1);
      }

      // When speaking with active jaw energy, mouth MUST open
      if (isSpeaking && jawEnergy > 0.1) {
        expect(weights.aa).toBeGreaterThan(0);
        expect(weights.aa).toBeLessThanOrEqual(1.0);
      }

      // When silent / not speaking, lip visemes must stay closed/calm
      if (!isSpeaking) {
        expect(weights.aa).toBe(0);
        expect(weights.ih).toBe(0);
      }
    }
  });

  it("evaluates 1,000 text-to-viseme timeline lookups for conversational speech", () => {
    const text = "Hello! I am HINAA, your personal AI companion. Let us build something amazing together today!";
    const durationMs = 4500;
    const events = textToVisemeEvents(text, durationMs);

    expect(events.length).toBeGreaterThan(0);

    for (let cycle = 0; cycle < 1000; cycle++) {
      const playTimeMs = (cycle / 1000) * durationMs;
      const viseme = getActiveViseme(playTimeMs, events);

      if (viseme) {
        expect(["aa", "ih", "ou", "oh", "ee", "closed"]).toContain(viseme.mouth);
        expect(viseme.weight).toBeGreaterThanOrEqual(0);
        expect(viseme.weight).toBeLessThanOrEqual(1.0);
      }
    }
  });

  it("benchmarks 1,000 stress frames under extreme parameter boundaries", () => {
    for (let cycle = 0; cycle < 1000; cycle++) {
      const extremeIntensity = (cycle % 2 === 0 ? -10 : 10) * Math.random();
      const extremeJaw = (cycle % 3 === 0 ? -5 : 5) * Math.random();

      const weights = buildVrmExpressionWeights({
        emotion: cycle % 2 === 0 ? "happy" : "surprised",
        intensity: extremeIntensity,
        jawEnergy: extremeJaw,
        blinking: cycle % 5 === 0,
        speaking: cycle % 2 === 0,
        reducedMotion: cycle % 4 === 0,
      });

      for (const key of VRM_EXPRESSION_KEYS) {
        const val = weights[key];
        expect(Number.isFinite(val)).toBe(true);
        expect(val).toBeGreaterThanOrEqual(0);
        expect(val).toBeLessThanOrEqual(1.0);
      }
    }
  });
});
