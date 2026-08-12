import { describe, expect, it } from "vitest";
import { expressionIntentFor } from "./companionExpression";

describe("companion expression director", () => {
  it("selects a warm celebratory accent from HINAA's reply text", () => {
    expect(expressionIntentFor("Congratulations, I am proud of you!", "speaking")).toBe("celebratory");
    expect(expressionIntentFor("कमाल, बहुत अच्छा किया।", "speaking")).toBe("celebratory");
  });

  it("selects empathy and concern without camera analysis", () => {
    expect(expressionIntentFor("I understand. I am here with you.", "speaking")).toBe("empathetic");
    expect(expressionIntentFor("There was an error, but we can retry safely.", "error")).toBe("concerned");
  });

  it("uses a warm neutral conversational presence when no cue is present", () => {
    expect(expressionIntentFor("", "listening")).toBe("warm");
    expect(expressionIntentFor("", "idle")).toBe("neutral");
  });
});
