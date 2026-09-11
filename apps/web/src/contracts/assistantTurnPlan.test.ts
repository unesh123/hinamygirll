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

  it("accepts nullable tool metadata and a model-proposed confirmation flag", () => {
    const plan = parseAssistantTurnPlan({
      ...validPlan,
      toolRequests: [{
        toolName: "image_generate",
        parameters: { prompt: "violet companion portrait" },
        userId: null,
        conversationId: null,
        confirmed: true,
      }],
    });
    expect(plan.toolRequests[0]?.toolName).toBe("image_generate");
  });

  it("passes through unknown and extra properties gracefully", () => {
    const plan = parseAssistantTurnPlan({ ...validPlan, extraField: "harmless_metadata" });
    expect((plan as any).extraField).toBe("harmless_metadata");
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

  it("accepts approvalSource, id, intent, and schemaVersion gracefully", () => {
    const plan = parseAssistantTurnPlan({
      ...validPlan,
      schemaVersion: 1,
      toolRequests: [{
        toolName: "image_search",
        parameters: { query: "gojo" },
        approvalSource: "standing-consent",
        id: "call-1",
        intent: "search images",
      }],
    });
    expect(plan.toolRequests[0]?.toolName).toBe("image_search");
    expect(plan.schemaVersion).toBe(1);
  });

  it("accepts tool and arguments aliases", () => {
    const plan = parseAssistantTurnPlan({
      ...validPlan,
      toolRequests: [{
        tool: "web_search",
        arguments: { query: "vite 6" },
      }],
    });
    expect(plan.toolRequests[0]?.toolName).toBe("web_search");
    expect(plan.toolRequests[0]?.parameters).toEqual({ query: "vite 6" });
  });

  it("accepts gateway toolRequests with null id, intent, reason, and approvalSource", () => {
    const plan = parseAssistantTurnPlan({
      ...validPlan,
      toolRequests: [{
        toolName: "image_search",
        parameters: { query: "gojo saturo", count: 6 },
        id: null,
        intent: null,
        reason: null,
        confirmed: false,
        approvalSource: "none",
        userId: null,
        conversationId: null,
      }],
    });
    expect(plan.toolRequests[0]?.toolName).toBe("image_search");
    expect(plan.toolRequests[0]?.parameters.query).toBe("gojo saturo");
  });
});
