import { describe, expect, it } from "vitest";
import { getSurfaceMotion, HINA_MOTION, getHinaTransition } from "./MOTION";

describe("The Walk motion vocabulary", () => {
  it("mirrors enter and exit so the surface settles on the curve it left on", () => {
    const walk = getSurfaceMotion(false);
    expect(walk.initial.y).toBe(walk.exit.y);
    expect(walk.initial.scale).toBe(walk.exit.scale);
    expect(walk.animate.y).toBe(0);
    expect(walk.animate.scale).toBe(1);
  });

  it("fades with a tween, not the layout spring", () => {
    const walk = getSurfaceMotion(false);
    const transition = walk.transition as Record<string, unknown>;
    expect(transition.type).toBe("spring");
    expect(transition.stiffness).toBe(520);
    expect(transition.opacity).toEqual({ duration: 0.18, ease: "easeOut" });
  });

  it("collapses to an instant snap under reduced motion", () => {
    const walk = getSurfaceMotion(true);
    expect(walk.transition).toBe(HINA_MOTION.reducedSnap);
    expect(walk.animate).toEqual({ opacity: 1 });
  });

  it("keeps the existing spring/settle helpers working", () => {
    expect(getHinaTransition(true)).toBe(HINA_MOTION.reducedSnap);
    expect(getHinaTransition(false, "settle")).toBe(HINA_MOTION.settle);
    expect(getHinaTransition(false, "spring")).toBe(HINA_MOTION.spring);
  });
});
