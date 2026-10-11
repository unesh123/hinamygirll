import { describe, expect, it } from "vitest";
import { rollBlinkShapeSpec } from "./blinkShape";

/** Deterministic rng cycling through the supplied values. */
const seq = (values: number[]) => {
  let i = 0;
  return () => values[i++ % values.length];
};

describe("rollBlinkShapeSpec", () => {
  it("rolls a near-full lid closure for the common blink", () => {
    // First roll < 0.78 → full close; subsequent rolls shape the envelope.
    const shape = rollBlinkShapeSpec(0, seq([0.1, 0.5, 0.5, 0.5, 0.5]));
    expect(shape.peak).toBeGreaterThanOrEqual(0.86);
    expect(shape.peak).toBeLessThanOrEqual(1.0);
  });

  it("rolls occasional partial blinks instead of never fully closing", () => {
    const shape = rollBlinkShapeSpec(0, seq([0.9, 0.5, 0.5, 0.5, 0.5]));
    expect(shape.peak).toBeGreaterThanOrEqual(0.48);
    expect(shape.peak).toBeLessThan(0.86);
  });

  it("keeps close fast and open slower, within human blink timing", () => {
    const shape = rollBlinkShapeSpec(0, seq([0.1, 1, 1, 1, 1]));
    expect(shape.close).toBeGreaterThanOrEqual(0.05);
    expect(shape.close).toBeLessThanOrEqual(0.085);
    expect(shape.open).toBeGreaterThan(shape.close);
    expect(shape.open).toBeLessThanOrEqual(0.21 + 1e-9);
  });

  it("drowsiness lengthens both phases of the blink", () => {
    const alert = rollBlinkShapeSpec(0, seq([0.1, 0, 0, 0, 0]));
    const drowsy = rollBlinkShapeSpec(1, seq([0.1, 0, 0, 0, 0]));
    expect(drowsy.close).toBeGreaterThan(alert.close);
    expect(drowsy.open).toBeGreaterThan(alert.open);
  });

  it("keeps lid asymmetry subtle", () => {
    const shape = rollBlinkShapeSpec(0, seq([0.1, 0.5, 0.5, 0.5, 1]));
    expect(shape.asym).toBeGreaterThanOrEqual(0.9);
    expect(shape.asym).toBeLessThanOrEqual(1.06);
  });
});
