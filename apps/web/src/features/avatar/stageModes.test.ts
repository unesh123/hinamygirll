/**
 * stageModes.test.ts — pure detectors for the cinematic stage's dynamic
 * modes: code mode (camera pulls wider, editor panel unfolds) and the
 * OtakuXWear chamber theme.
 */
import { describe, expect, it } from "vitest";
import {
  extractCodeBlock,
  hasCodeBlock,
  isOtakuXWearTopic,
  splitIntoPhrases,
} from "./stageModes";

describe("hasCodeBlock / extractCodeBlock", () => {
  it("detects a fenced code block and returns its body", () => {
    const text = [
      "Here's how it works:",
      "```python",
      "def hi():",
      "    return 1",
      "```",
      "That's the whole thing.",
    ].join("\n");
    expect(hasCodeBlock(text)).toBe(true);
    const body = extractCodeBlock(text);
    expect(body).toContain("def hi():");
    expect(body).toContain("return 1");
  });

  it("does not treat the bare word 'code' as code mode", () => {
    // The persona itself talks about code-switching — a false positive here
    // would flip the whole stage into editor mode on casual chat.
    expect(hasCodeBlock("what code are you using?")).toBe(false);
    expect(hasCodeBlock("code-switching is natural")).toBe(false);
  });

  it("ignores empty blocks and empty input", () => {
    expect(extractCodeBlock("```\n```")).toBe(null);
    expect(extractCodeBlock("```python\n```")).toBe(null);
    expect(extractCodeBlock("")).toBe(null);
    expect(extractCodeBlock(null)).toBe(null);
  });
});

describe("isOtakuXWearTopic", () => {
  it("matches the brand in any casing", () => {
    expect(isOtakuXWearTopic("tell me about OtakuXWear")).toBe(true);
    expect(isOtakuXWearTopic("otakuxwear store")).toBe(true);
    expect(isOtakuXWearTopic("OTAKU X WEAR")).toBe(true);
    expect(isOtakuXWearTopic("otaku wear shop")).toBe(true);
  });

  it("matches anime-commerce phrases", () => {
    expect(isOtakuXWearTopic("anime merch")).toBe(true);
    expect(isOtakuXWearTopic("anime-commerce ideas")).toBe(true);
  });

  it("rejects unrelated chat", () => {
    expect(isOtakuXWearTopic("how are you today")).toBe(false);
    expect(isOtakuXWearTopic("what anime should I watch")).toBe(false);
    expect(isOtakuXWearTopic(null)).toBe(false);
    expect(isOtakuXWearTopic("")).toBe(false);
  });
});

describe("splitIntoPhrases", () => {
  it("splits on sentence boundaries, not per character", () => {
    const phrases = splitIntoPhrases("Hello! How are you? म ठिक छु।");
    expect(phrases.length).toBeGreaterThanOrEqual(3);
    expect(phrases[0]).toBe("Hello!");
    expect(phrases[1]).toBe("How are you?");
  });

  it("returns nothing for blank input", () => {
    expect(splitIntoPhrases("")).toEqual([]);
    expect(splitIntoPhrases("   ")).toEqual([]);
    expect(splitIntoPhrases(null)).toEqual([]);
  });

  it("caps the number of phrases", () => {
    const long = Array.from({ length: 30 }, () => "Sentence here.").join(" ");
    expect(splitIntoPhrases(long).length).toBeLessThanOrEqual(12);
  });
});
