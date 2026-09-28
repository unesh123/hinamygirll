import { describe, expect, it } from "vitest";
import { extractBrainThought } from "./brainThoughtExtractor";

describe("brainThoughtExtractor", () => {
  it("extracts closed <think> tag and cleans response text", () => {
    const raw = "<think>Let me analyze the request.</think>Hello, I am ready.";
    const result = extractBrainThought(raw);
    expect(result.thought).toBe("Let me analyze the request.");
    expect(result.cleanText).toBe("Hello, I am ready.");
  });

  it("extracts closed <thought> tag and cleans response text", () => {
    const raw = "<thought>Calculating 2 + 2 = 4</thought>The answer is 4.";
    const result = extractBrainThought(raw);
    expect(result.thought).toBe("Calculating 2 + 2 = 4");
    expect(result.cleanText).toBe("The answer is 4.");
  });

  it("extracts unclosed <think> tag during live streaming", () => {
    const raw = "<think>Drafting ideas";
    const result = extractBrainThought(raw);
    expect(result.thought).toBe("Drafting ideas");
    expect(result.cleanText).toBe("");
  });

  it("combines planThinking with extracted tags", () => {
    const raw = "<think>Tag thought</think>Actual text";
    const result = extractBrainThought(raw, "Plan thought");
    expect(result.thought).toContain("Plan thought");
    expect(result.thought).toContain("Tag thought");
    expect(result.cleanText).toBe("Actual text");
  });

  it("leaves plain text untouched if no think tags exist", () => {
    const raw = "Just normal conversational text.";
    const result = extractBrainThought(raw);
    expect(result.thought).toBe("");
    expect(result.cleanText).toBe("Just normal conversational text.");
  });
});
