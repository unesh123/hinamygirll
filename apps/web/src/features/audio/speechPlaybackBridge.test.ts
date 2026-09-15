import { describe, expect, it } from "vitest";
import { idleSpeechPlayback, sampleSpeechPlayback } from "./speechPlaybackBridge";

describe("shared speech playback clock", () => {
  it("keeps queued, paused and reset speech silent and samples exact playback time", () => {
    let time = -20;
    const bridge = { current: { ...idleSpeechPlayback(), state: "queued" as "queued" | "playing" | "paused", elapsedMs: () => time,
      events: [{ timeMs: 0, durationMs: 100, mouth: "aa" as const, weight: 0.8 }] } };
    expect(sampleSpeechPlayback(bridge).speaking).toBe(false);
    bridge.current.state = "playing";
    expect(sampleSpeechPlayback(bridge).speaking).toBe(false);
    time = 50;
    expect(sampleSpeechPlayback(bridge).viseme?.mouth).toBe("aa");
    bridge.current.state = "paused";
    expect(sampleSpeechPlayback(bridge).viseme).toBeNull();
    const reset = { current: idleSpeechPlayback() };
    expect(sampleSpeechPlayback(reset).speaking).toBe(false);
  });
});
