import { describe, expect, it } from "vitest";
import { getActiveViseme, textToVisemeEvents } from "./textToViseme";

describe("textToVisemeEvents", () => {
  it("returns no events for empty text or duration", () => {
    expect(textToVisemeEvents("", 1000)).toEqual([]);
    expect(textToVisemeEvents("hello", 0)).toEqual([]);
    expect(textToVisemeEvents("...", 1000)).toEqual([]);
  });

  it("keeps Latin/romanized Nepali behaviour", () => {
    const events = textToVisemeEvents("namaste", 700);
    expect(events.length).toBeGreaterThan(0);
    const total = events.reduce((sum, e) => sum + e.durationMs, 0);
    expect(total).toBeCloseTo(700, 5);
  });

  it("produces events for Devanagari Nepali text", () => {
    // "नमस्ते" — previously produced zero events (Latin-only filter)
    const events = textToVisemeEvents("नमस्ते", 700);
    expect(events.length).toBeGreaterThan(0);
    const total = events.reduce((sum, e) => sum + e.durationMs, 0);
    expect(total).toBeCloseTo(700, 5);
  });

  it("maps Devanagari consonants to open mouth (inherent schwa)", () => {
    const events = textToVisemeEvents("क", 100);
    expect(events).toHaveLength(1);
    expect(events[0].mouth).toBe("aa");
  });

  it("applies matra override to the preceding syllable", () => {
    // "की" — consonant क (aa) then matra ी reshapes to ee
    const events = textToVisemeEvents("की", 200);
    expect(events).toHaveLength(1);
    expect(events[0].mouth).toBe("ee");
  });

  it("closes the mouth on virama clusters", () => {
    // "स्त" — स (aa), virama (closed), त (aa)
    const events = textToVisemeEvents("स्त", 300);
    expect(events.map((e) => e.mouth)).toEqual(["aa", "closed", "aa"]);
  });

  it("maps independent vowels directly", () => {
    // "आ" → aa, "ई" → ee, "ओ" → ou
    expect(textToVisemeEvents("आ", 100)[0].mouth).toBe("aa");
    expect(textToVisemeEvents("ई", 100)[0].mouth).toBe("ee");
    expect(textToVisemeEvents("ओ", 100)[0].mouth).toBe("ou");
  });

  it("handles mixed Nepali-English code-switched text", () => {
    const events = textToVisemeEvents("मलाई assignment बुझाऊ", 1200);
    expect(events.length).toBeGreaterThan(3);
    const mouths = new Set(events.map((e) => e.mouth));
    expect(mouths.size).toBeGreaterThan(1);
  });

  it("supports getActiveViseme over a Devanagari timeline", () => {
    const events = textToVisemeEvents("नमस्ते", 600);
    expect(getActiveViseme(0, events)?.mouth).toBeTruthy();
    expect(getActiveViseme(299, events)?.mouth).toBeTruthy();
    expect(getActiveViseme(601, events)).toBeNull();
  });
});
