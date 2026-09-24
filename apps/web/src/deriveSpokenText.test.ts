import { describe, expect, it } from "vitest";
import { deriveSpokenText } from "./features/audio/deriveSpokenText";

describe("deriveSpokenText", () => {
  it("returns empty string for empty input", () => {
    expect(deriveSpokenText("")).toBe("");
  });

  it("preserves plain text unchanged", () => {
    const input = "Hello, how are you today?";
    expect(deriveSpokenText(input)).toBe(input);
  });

  it("removes fenced code blocks", () => {
    const input = "Here is a function:\n```js\nconst x = 1;\n```\nPretty simple.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("```");
    expect(result).not.toContain("const x = 1");
    expect(result).toContain("Pretty simple");
  });

  it("removes inline code but keeps content", () => {
    const input = "Use the `useState` hook for state.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("`");
    expect(result).toContain("useState");
  });

  it("removes markdown links but keeps link text", () => {
    const input = "Check [this guide](https://example.com) for details.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("https://");
    expect(result).toContain("this guide");
  });

  it("removes bare URLs", () => {
    const input = "Visit https://example.com/path?q=1 for more info.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("https://");
    expect(result).toContain("for more info");
  });

  it("removes citation IDs", () => {
    const input = "According to research [1] and findings [2], this works [^note].";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("[1]");
    expect(result).not.toContain("[2]");
    expect(result).not.toContain("[^note]");
  });

  it("removes headings", () => {
    const input = "# Title\n## Subtitle\nRegular text.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("#");
    expect(result).toContain("Title");
    expect(result).toContain("Regular text");
  });

  it("removes bold/italic markers but keeps content", () => {
    const input = "This is **bold** and *italic* and __both__.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("**");
    expect(result).not.toContain("*");
    expect(result).toContain("bold");
    expect(result).toContain("italic");
  });

  it("removes table rows", () => {
    const input = "| Name | Value |\n|------|-------|\n| foo | bar |\nSome text.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("|");
    expect(result).toContain("Some text");
  });

  it("removes blockquote markers", () => {
    const input = "> This is a quote.\n> Still quoted.\nRegular text.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain(">");
    expect(result).toContain("This is a quote");
  });

  it("removes image markdown", () => {
    const input = "Look at this ![photo](https://img.png) image.";
    const result = deriveSpokenText(input);
    expect(result).not.toContain("![");
    expect(result).not.toContain("https://img.png");
    expect(result).toContain("image");
  });

  it("preserves Devanagari text", () => {
    const input = "नमस्ते, आज मौसम कैसा है?";
    expect(deriveSpokenText(input)).toBe(input);
  });

  it("preserves mixed Hindi-English text", () => {
    const input = "HINAA बहुत अच्छी है। She helps me every day.";
    expect(deriveSpokenText(input)).toBe(input);
  });

  it("preserves decimal points in numbers", () => {
    const input = "The value is 3.14 and the rate is 9.8%";
    expect(deriveSpokenText(input)).toBe(input);
  });

  it("preserves abbreviations like Dr. and Mr.", () => {
    const input = "Dr. Smith said Mr. Jones agreed.";
    expect(deriveSpokenText(input)).toBe(input);
  });

  it("truncates at sentence boundary for long text", () => {
    // Input must exceed 280 chars (MAX_SPOKEN_LENGTH) to trigger truncation
    const longMiddle = " The additional content continues here with more words".repeat(6);
    const input = "First sentence. Second sentence. Third sentence. Fourth sentence." + longMiddle + " Final wrap up sentence.";
    const result = deriveSpokenText(input);
    expect(result.length).toBeLessThan(input.length);
    expect(result).toContain("First sentence");
    // Should end at a sentence boundary (period from the kept sentence)
    expect(result).toMatch(/[.!?:]$/);
  });

  it("adds continuation hint when there is more content", () => {
    const input = "A".repeat(300) + ". More content follows here.";
    const result = deriveSpokenText(input);
    expect(result).toContain("Details are available in the chat");
  });

  it("does not alter the original displayText", () => {
    const displayText = "# Title\n```code```\n[link](url)\n**bold** *italic*";
    const original = displayText;
    deriveSpokenText(displayText);
    expect(displayText).toBe(original);
  });
});
