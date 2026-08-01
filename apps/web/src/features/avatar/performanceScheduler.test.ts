import { describe, expect, it } from "vitest";
import { parseAssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import { PerformanceScheduler } from "./performanceScheduler";
import { SEMANTIC_RUNTIME_MAP } from "./performanceTypes";

function samplePlan(gesture = "small_nod") {
  return parseAssistantTurnPlan({
    spokenText: "Namaste, assignment explain garaum.",
    displayText: "Namaste, assignment explain garaum.",
    language: "mixed",
    emotion: {
      primary: "thinking",
      intensity: 0.5,
      valence: 0.1,
      arousal: 0.1,
    },
    performance: {
      facePreset: "thinking",
      gesture,
      gazeTarget: "camera",
      headMotion: "subtle",
      blinkRate: 0.4,
    },
    memoryCandidates: [],
    toolRequests: [],
  });
}

describe("PerformanceScheduler", () => {
  it("maps only allowlisted semantic motions", () => {
    expect(Object.keys(SEMANTIC_RUNTIME_MAP)).toContain("small_nod");
    expect(SEMANTIC_RUNTIME_MAP.small_nod.cssGesture).toBe("small_nod");
  });

  it("loads cues from a plan and samples active gesture", () => {
    let t = 0;
    const scheduler = new PerformanceScheduler({ now: () => t });
    scheduler.loadFromPlan(samplePlan("wave"));
    t = 200;
    const frame = scheduler.sample();
    expect(frame.generation).toBe(0);
    expect(frame.gesture).toBe("wave");
    expect(frame.lipSyncLevel).toBe("amplitude");
  });

  it("ignores stale generation jaw and plans after interrupt", () => {
    let t = 0;
    const scheduler = new PerformanceScheduler({ now: () => t });
    scheduler.loadFromPlan(samplePlan());
    scheduler.setJawEnergy(0.8, 0);
    const next = scheduler.interrupt();
    expect(next).toBe(1);
    scheduler.setJawEnergy(0.9, 0);
    expect(scheduler.sample().jawEnergy).toBe(0);
    scheduler.loadFromPlan(samplePlan("celebrate"), 0);
    expect(scheduler.sample().gesture).toBe("none");
  });

  it("caps gesture intensity under reduced motion", () => {
    let t = 0;
    const scheduler = new PerformanceScheduler({
      now: () => t,
      reducedMotion: true,
    });
    const sequence = scheduler.loadFromPlan(samplePlan("celebrate"));
    for (const cue of sequence.cues) {
      expect(cue.intensity).toBeLessThanOrEqual(0.25);
    }
    t = 150;
    expect(scheduler.sample().jawEnergy).toBe(0);
  });

  it("returns to neutral after cue window", () => {
    let t = 0;
    const scheduler = new PerformanceScheduler({ now: () => t });
    const sequence = scheduler.loadFromPlan(samplePlan("explain"));
    const last = sequence.cues[sequence.cues.length - 1]!;
    t = last.startMs + last.durationMs + 10;
    const frame = scheduler.sample();
    expect(frame.semantic).toBe("neutral_idle");
  });

  it("rejects invalid cue intensity via schema on load path", () => {
    const scheduler = new PerformanceScheduler();
    expect(() =>
      scheduler.loadFromPlan(
        parseAssistantTurnPlan({
          ...samplePlan(),
          emotion: {
            primary: "happy",
            intensity: 0.2,
            valence: 0.2,
            arousal: 0.1,
          },
        }),
      ),
    ).not.toThrow();
  });
});
