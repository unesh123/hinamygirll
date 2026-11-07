import { describe, expect, it } from "vitest";
import { fitDistance, framesHands, HANDS_FROM_TOP, handsFramingSpan, type FramingAnatomy } from "./companionFraming";

const anatomy: FramingAnatomy = { headY: 1.38, neckY: 1.28, chestY: 1.12, hipsY: 0.80, minY: 0, maxY: 1.55, width: 0.62 };

describe("companion framing", () => {
  it("only reframes tall docks, not wide stages", () => {
    expect(framesHands(320 / 545)).toBe(true);
    expect(framesHands(1.6)).toBe(false);
    expect(framesHands(Number.NaN)).toBe(false);
    expect(framesHands(0)).toBe(false);
  });

  it("keeps hanging hands (just under the hips) above the dock's subtitle overlay", () => {
    const top = anatomy.headY + 0.1;
    const span = handsFramingSpan(anatomy, top);
    const handsY = anatomy.hipsY - 0.28 * 0.42;
    const fromTop = (span.top - handsY) / (span.top - span.bottom);
    expect(span.top).toBe(top);
    expect(span.bottom).toBeLessThan(handsY);
    expect(fromTop).toBeCloseTo(HANDS_FROM_TOP, 5);
    expect(fromTop).toBeLessThan(0.7);
  });

  it("fits both height and width of the body", () => {
    const aspect = 320 / 545;
    const fov = 24;
    const distance = fitDistance(1.0, anatomy.width ?? 0, fov, aspect);
    const tangent = Math.tan(fov * Math.PI / 360);
    expect(distance * tangent).toBeGreaterThanOrEqual(0.5);
    expect(distance * tangent * aspect).toBeGreaterThanOrEqual(anatomy.width! / 2);
    expect(fitDistance(0.1, 3, 30, 1)).toBeGreaterThan(fitDistance(0.1, 0.3, 30, 1));
  });
});
