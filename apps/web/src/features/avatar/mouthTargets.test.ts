import { describe, expect, it } from "vitest";
import {
  computeCoarticulatedMouthTarget,
  COARTICULATION_FACTOR,
} from "./mouthTargets";
import type { VisemeEvent } from "../audio/textToViseme";

const ev = (mouth: VisemeEvent["mouth"], weight = 0.9): VisemeEvent => ({
  timeMs: 0,
  durationMs: 80,
  mouth,
  weight,
});

describe("computeCoarticulatedMouthTarget", () => {
  it("returns the active viseme as the primary target scaled by energy", () => {
    const t = computeCoarticulatedMouthTarget(ev("aa"), null, 0.8);
    expect(t.mouth).toBe("aa");
    expect(t.weight).toBeCloseTo(0.9 * 0.8, 5);
    expect(t.lookaheadMouth).toBeNull();
    expect(t.lookaheadWeight).toBe(0);
  });

  it("keeps a minimum visible weight so quiet speech still articulates", () => {
    const t = computeCoarticulatedMouthTarget(ev("ih", 0.05), null, 0.5);
    expect(t.mouth).toBe("ih");
    expect(t.weight).toBeGreaterThanOrEqual(0.10);
  });

  it("blends the upcoming viseme at the coarticulation factor when it differs", () => {
    const t = computeCoarticulatedMouthTarget(ev("aa"), ev("ou"), 1);
    expect(t.mouth).toBe("aa");
    expect(t.lookaheadMouth).toBe("ou");
    expect(t.lookaheadWeight).toBeCloseTo(0.9 * 1 * COARTICULATION_FACTOR, 5);
  });

  it("does not double-drive a mouth when the upcoming shape matches the active one", () => {
    const t = computeCoarticulatedMouthTarget(ev("ee"), ev("ee"), 1);
    expect(t.lookaheadMouth).toBeNull();
    expect(t.lookaheadWeight).toBe(0);
  });

  it("treats closed visemes as silence for both targets", () => {
    const t = computeCoarticulatedMouthTarget(ev("closed"), ev("closed"), 1);
    expect(t.mouth).toBeNull();
    expect(t.weight).toBe(0);
    expect(t.lookaheadMouth).toBeNull();
  });

  it("still anticipates the next phoneme out of a silence gap", () => {
    const t = computeCoarticulatedMouthTarget(ev("closed"), ev("oh", 0.7), 1);
    expect(t.mouth).toBeNull();
    expect(t.lookaheadMouth).toBe("oh");
    expect(t.lookaheadWeight).toBeGreaterThan(0);
  });

  it("handles null active and upcoming events (no timeline)", () => {
    const t = computeCoarticulatedMouthTarget(null, null, 1);
    expect(t.mouth).toBeNull();
    expect(t.lookaheadMouth).toBeNull();
  });
});
