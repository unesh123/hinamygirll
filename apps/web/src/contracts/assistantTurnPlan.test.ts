import { describe, expect, it } from "vitest";
import { parseAssistantTurnPlan } from "./assistantTurnPlan";

const validPlan = {
  spokenText: "Namaste!",
  displayText: "Namaste!",
  language: "mixed",
  emotion: { primary: "happy", intensity: 0.5, valence: 0.4, arousal: 0.2 },
  performance: {
    facePreset: "soft_smile",
    gesture: "wave",
    gazeTarget: "camera",
    headMotion: "subtle",
    blinkRate: 0.45,
  },
  memoryCandidates: [],
  toolRequests: [],
};

describe("AssistantTurnPlan validation", () => {
  it("accepts an allowlisted plan", () => {
    expect(parseAssistantTurnPlan(validPlan).emotion.primary).toBe("happy");
  });

  it("rejects animation filenames and unknown properties", () => {
    expect(() =>
      parseAssistantTurnPlan({ ...validPlan, animationFile: "wave.vrma" }),
    ).toThrow();
  });

  it("rejects tool requests and out-of-range intensity", () => {
    expect(() =>
      parseAssistantTurnPlan({
        ...validPlan,
        emotion: { ...validPlan.emotion, intensity: 2 },
        toolRequests: [{ tool: "shell" }],
      }),
    ).toThrow();
  });
});
