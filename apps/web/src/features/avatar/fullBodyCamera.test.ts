import { describe, expect, it } from "vitest";
import { fullBodyCameraDistance } from "./fullBodyCamera";

describe("full-body camera", () => {
  it.each([0.45, 0.65, 1, 1.8])("fits feet, head and lateral walk travel at aspect %s", aspect => {
    const height = 1.8, width = 0.9, depth = 0.4;
    const distance = fullBodyCameraDistance(height, width, aspect, 43, depth);
    const halfVisibleHeight = (distance - depth / 2) * Math.tan(43 * Math.PI / 360);
    expect(halfVisibleHeight).toBeGreaterThanOrEqual(height / 2 * 1.35);
    expect(halfVisibleHeight * aspect).toBeGreaterThanOrEqual((width / 2 + 0.28) * 1.35 - 1e-10);
  });
});
