import { describe, expect, it } from "vitest";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import {
  deserializeAssistantTurn,
  getAssistantArtifacts,
  getAssistantDisplayText,
  getAssistantSpokenText,
  getSafeAssistantStreamingText,
  serializeAssistantTurn,
} from "./assistantTurnCodec";

const turn: AssistantTurnPlan = {
  displayText: "# Detailed answer\n\nThis is the **complete** technical explanation.",
  spokenText: "Here is the short technical takeaway.",
  language: "en-US",
  emotion: { primary: "thinking", intensity: 0.3, valence: 0.1, arousal: 0.1 },
  performance: { facePreset: "thinking", gesture: "explain", gazeTarget: "camera", headMotion: "subtle", blinkRate: 0.4 },
  memoryCandidates: [],
  toolRequests: [{ toolName: "diagnostic_echo", parameters: { message: "ok" } }],
};

describe("assistant turn codec", () => {
  it("preserves detailed display text and a distinct concise speech route", () => {
    const content = serializeAssistantTurn(turn);
    expect(getAssistantDisplayText(content)).toBe(turn.displayText);
    expect(getAssistantSpokenText(content)).toBe(turn.spokenText);
    expect(getAssistantSpokenText(content)).not.toContain("#");
  });

  it("round-trips structured plans and retains tool artifacts", () => {
    const content = serializeAssistantTurn(turn);
    expect(deserializeAssistantTurn(content)).toEqual(turn);
    expect(getAssistantArtifacts(content)).toEqual(turn.toolRequests);
  });

  it("keeps legacy plain text readable", () => {
    expect(deserializeAssistantTurn("Older assistant answer.")).toBeUndefined();
    expect(getAssistantDisplayText("Older assistant answer.")).toBe("Older assistant answer.");
    expect(getAssistantSpokenText("Older assistant answer.")).toBe("Older assistant answer.");
  });

  it("never exposes an invalid prefixed structured payload as raw JSON", () => {
    const broken = "hinaa.assistant-turn/v1:{not valid json";
    expect(deserializeAssistantTurn(broken)).toBeUndefined();
    expect(getAssistantDisplayText(broken)).toBe("A saved response could not be restored safely.");
  });

  it("holds a partial fenced HINAA plan until it can render display text", () => {
    const partial = "```json\n{\n  \"spokenText\": \"Hey babe!\",";
    const fenced = `\`\`\`json\n${JSON.stringify(turn)}\n\`\`\``;
    expect(getSafeAssistantStreamingText(partial)).toBe("");
    expect(getSafeAssistantStreamingText(fenced)).toBe(turn.displayText);
  });
});


  it("decodes a Markdown-fenced Claude plan without exposing JSON to chat or speech", () => {
    const fenced = `\`\`\`json\n${JSON.stringify(turn)}\n\`\`\``;
    expect(deserializeAssistantTurn(fenced)).toEqual(turn);
    expect(getAssistantDisplayText(fenced)).toBe(turn.displayText);
    expect(getAssistantSpokenText(fenced)).toBe(turn.spokenText);
    expect(getAssistantDisplayText(fenced)).not.toContain("\`\`\`json");
  });
