import { describe, expect, it } from "vitest";
import {
  createLipSyncTimeline,
  getActiveViseme,
  normalizeProviderVisemeEvents,
  textToVisemeEvents,
} from "./textToViseme";

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

  it("spends audio time on pauses so the mouth never leads the voice", () => {
    const withPause = textToVisemeEvents("hello, world", 1_000);
    const withoutPause = textToVisemeEvents("helloworld", 1_000);

    // Identical letters, so the only difference is the time the comma and the
    // space take. The last syllable has to arrive later when they do; uniform
    // per-letter timing pushed it early and the mouth led the audio all way.
    const lastStart = (events: typeof withPause) =>
      events[events.length - 1].timeMs;
    expect(lastStart(withPause)).toBeGreaterThan(lastStart(withoutPause));
  });

  it("rests the mouth at a pause and spans the whole clip", () => {
    const events = textToVisemeEvents("Namaste. K cha?", 900);
    const closures = events.filter((e) => e.mouth === "closed");
    expect(closures.length).toBeGreaterThanOrEqual(2);
    expect(closures.every((e) => e.weight < 0.2)).toBe(true);

    const last = events[events.length - 1];
    expect(last.timeMs + last.durationMs).toBeCloseTo(900, 5);
  });

  it("gives a held vowel more time than a stop consonant", () => {
    const [vowel, consonant] = textToVisemeEvents("at", 100);
    expect(vowel.mouth).toBe("aa");
    expect(consonant.mouth).toBe("ih");
    expect(vowel.durationMs).toBeGreaterThan(consonant.durationMs);
  });

  it("prioritizes provider-timed visemes over text fallback when available", () => {
    const events = createLipSyncTimeline({
      text: "namaste",
      durationMs: 700,
      providerEvents: [
        { timeMs: 120, durationMs: 80, mouth: "oh", weight: 0.8 },
        { timeMs: 0, durationMs: 100, mouth: "aa", weight: 1.2 },
      ],
    });

    expect(events).toEqual([
      { timeMs: 0, durationMs: 100, mouth: "aa", weight: 1 },
      { timeMs: 120, durationMs: 80, mouth: "oh", weight: 0.8 },
    ]);
  });

  it("normalizes provider visemes into the active audio chunk window", () => {
    const events = normalizeProviderVisemeEvents(
      [
        { timeMs: -50, durationMs: 20, mouth: "ee", weight: -1 },
        { timeMs: 2_000, durationMs: 500, mouth: "ou", weight: 0.7 },
      ],
      1_000,
      250,
    );

    expect(events[0]).toEqual({ timeMs: 250, durationMs: 20, mouth: "ee", weight: 0 });
    expect(events[1]).toEqual({ timeMs: 1250, durationMs: 16, mouth: "ou", weight: 0.7 });
  });
});
