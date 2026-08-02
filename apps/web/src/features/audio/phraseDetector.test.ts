import { describe, expect, it } from "vitest";
import { PhraseDetector } from "./phraseDetector";

describe("PhraseDetector", () => {
  it("emits on sentence boundaries for Devanagari and Latin", () => {
    const detector = new PhraseDetector({
      minPhraseChars: 4,
      maxBufferChars: 80,
    });
    expect(detector.push("Namaste. ")).toEqual(["Namaste."]);
    expect(detector.push("नमस्ते। ")).toEqual(["नमस्ते।"]);
  });

  it("handles Romanized Nepali and Hindi chunks", () => {
    const detector = new PhraseDetector({
      minPhraseChars: 8,
      maxBufferChars: 120,
    });
    const out = detector.push(
      "Ma aile short response deu. Ab Hindi mein batao. ",
    );
    expect(out.length).toBeGreaterThan(0);
    expect(out.join(" ")).toMatch(/response|Hindi/i);
  });

  it("handles mixed Nepali-English chunks", () => {
    const detector = new PhraseDetector({
      minPhraseChars: 8,
      maxBufferChars: 120,
    });
    const out = [
      ...detector.push("Yo bug TypeError ho. "),
      ...detector.push("Pahila stack trace herau."),
    ];
    expect(out[0]).toMatch(/TypeError/);
  });

  it("does not split file paths, URLs, decimals, or env vars eagerly", () => {
    const detector = new PhraseDetector({
      minPhraseChars: 4,
      maxBufferChars: 40,
    });
    const phrases = detector.push(
      "See https://example.com/x and apps/web/src/App.tsx and HINAA_DATABASE_URL and 3.14 next ",
    );
    const joined = phrases.join(" ");
    expect(joined).not.toMatch(/App\.ts$/);
    expect(joined.includes("3.") && !joined.includes("3.14")).toBe(false);
  });

  it("forces a phrase after max buffer", () => {
    const detector = new PhraseDetector({
      minPhraseChars: 4,
      maxBufferChars: 24,
    });
    const long = "word ".repeat(20);
    const phrases = detector.push(long);
    expect(phrases.length).toBeGreaterThan(0);
  });

  it("flushes remainder and resets on cancel", () => {
    const detector = new PhraseDetector();
    detector.push("incomplete buffer");
    expect(detector.flush()).toEqual(["incomplete buffer"]);
    expect(detector.pending()).toBe("");
    detector.push("stale");
    detector.reset();
    expect(detector.pending()).toBe("");
  });
});
