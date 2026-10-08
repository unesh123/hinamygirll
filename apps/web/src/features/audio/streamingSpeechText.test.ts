import { describe, expect, it } from "vitest";
import { cleanSpeechText, StreamingSpeechText } from "./streamingSpeechText";
import { getSafeAssistantStreamingText } from "../companion/assistantTurnCodec";

describe("streamed spoken content", () => {
  it("drains every complete sentence in a single delta", () => {
    const stream = new StreamingSpeechText();
    expect(stream.push("First sentence. Second sentence. Third sentence. ")).toEqual(["First sentence.", "Second sentence.", "Third sentence."]);
    expect(stream.flush()).toEqual([]);
  });
  it("does not repeat identical snapshots, final flushes or adjacent sentences", () => {
    const stream = new StreamingSpeechText();
    expect(stream.push("Hello there. Hello there. ")).toEqual(["Hello there."]);
    expect(stream.push("Hello there. Hello there. ")).toEqual([]);
    expect(stream.flush()).toEqual([]);
  });
  it("keeps reasoning and code out of speech", () => {
    const stream = new StreamingSpeechText();
    expect(stream.push(getSafeAssistantStreamingText("<think>Private thoughts. "))).toEqual([]);
    expect(stream.push(getSafeAssistantStreamingText("<think>Private thoughts.</think>Visible reply. "))).toEqual(["Visible reply."]);
    expect(cleanSpeechText("Answer.\n```ts\nsecret();\n```\nMore." )).not.toContain("secret");
  });
  it("preserves a substantive answer instead of clipping it to one sentence", () => {
    const long = "Useful complete explanation. ".repeat(30);
    expect(cleanSpeechText(long)).toBe(long);
  });
});
