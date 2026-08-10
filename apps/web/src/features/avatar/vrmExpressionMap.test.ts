import { describe, expect, it } from "vitest";
import {
  buildVrmExpressionWeights,
  VRM_EXPRESSION_KEYS,
  type VrmExpressionInput,
} from "./vrmExpressionMap";

function base(overrides: Partial<VrmExpressionInput> = {}): VrmExpressionInput {
  return {
    emotion: "neutral",
    intensity: 0.5,
    jawEnergy: 0,
    blinking: false,
    speaking: false,
    reducedMotion: false,
    ...overrides,
  };
}

describe("buildVrmExpressionWeights", () => {
  it("keeps neutral calm when idle", () => {
    const weights = buildVrmExpressionWeights(base());
    expect(weights.happy).toBe(0);
    expect(weights.sad).toBe(0);
    expect(weights.surprised).toBe(0);
    expect(weights.relaxed).toBeGreaterThan(0);
  });

  it("maps happy emotion to happy preset scaled by intensity", () => {
    const strong = buildVrmExpressionWeights(base({ emotion: "happy", intensity: 1 }));
    const weak = buildVrmExpressionWeights(base({ emotion: "happy", intensity: 0.2 }));
    expect(strong.happy).toBeCloseTo(0.55, 2);
    expect(weak.happy).toBeCloseTo(0.11, 2);
    expect(strong.happy).toBeGreaterThan(weak.happy);
  });

  it("maps surprised to the surprised preset", () => {
    const weights = buildVrmExpressionWeights(
      base({ emotion: "surprised", intensity: 0.8 }),
    );
    expect(weights.surprised).toBeCloseTo(0.68, 2);
    expect(weights.aa).toBeCloseTo(0.32, 2);
  });

  it("drives open visemes from jaw energy while speaking", () => {
    const silent = buildVrmExpressionWeights(base({ speaking: true, jawEnergy: 0 }));
    const talking = buildVrmExpressionWeights(base({ speaking: true, jawEnergy: 0.8 }));
    expect(silent.aa).toBe(0);
    expect(talking.aa).toBeCloseTo(0.72, 2);
    expect(talking.aa).toBeGreaterThan(talking.ou);
    expect(talking.ou).toBeGreaterThan(0);
  });

  it("does not lip-sync when not speaking even with jaw energy", () => {
    const weights = buildVrmExpressionWeights(base({ speaking: false, jawEnergy: 0.9 }));
    expect(weights.aa).toBe(0);
    expect(weights.ih).toBe(0);
  });

  it("blinks fully on blink beats and not otherwise", () => {
    const open = buildVrmExpressionWeights(base({ blinking: false }));
    const closed = buildVrmExpressionWeights(base({ blinking: true }));
    expect(open.blink).toBe(0);
    expect(closed.blink).toBe(1);
    expect(closed.blinkLeft).toBe(1);
    expect(closed.blinkRight).toBe(1);
  });

  it("applies face presets on top of the emotion", () => {
    const weights = buildVrmExpressionWeights(
      base({ emotion: "neutral", facePreset: "big_smile", intensity: 0.5 }),
    );
    expect(weights.happy).toBeCloseTo(1, 2);
  });

  it("clamps all weights to 0..1", () => {
    const weights = buildVrmExpressionWeights(
      base({ emotion: "excited", facePreset: "big_smile", intensity: 2, jawEnergy: 2, speaking: true }),
    );
    for (const key of VRM_EXPRESSION_KEYS) {
      expect(weights[key]).toBeGreaterThanOrEqual(0);
      expect(weights[key]).toBeLessThanOrEqual(1);
    }
  });

  it("calms every expression under reduced motion", () => {
    const full = buildVrmExpressionWeights(base({ emotion: "happy", intensity: 1 }));
    const calm = buildVrmExpressionWeights(
      base({ emotion: "happy", intensity: 1, reducedMotion: true, blinking: true }),
    );
    expect(calm.happy).toBeLessThan(full.happy);
    expect(calm.happy).toBeGreaterThan(0);
    // Reduced motion scales non-blink weights to 40%.
    expect(calm.happy).toBeCloseTo(full.happy * 0.4, 2);
    // Reduced motion kills blink animation but keeps a still blink safe.
    expect(calm.blink).toBe(0);
  });

  it("returns rounded 3-decimal weights", () => {
    const weights = buildVrmExpressionWeights(base({ emotion: "playful", intensity: 0.37 }));
    for (const value of Object.values(weights)) {
      expect(Math.round(value * 1000) / 1000).toBe(value);
    }
  });
});
