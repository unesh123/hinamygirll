import { describe, expect, it } from "vitest";
import { LocalVad } from "./liveVad";

const testOptions = {
  startThreshold: 0.02,
  speakerThreshold: 0.08,
  startFrames: 2,
  minimumSpeechFrames: 3,
  silenceFrames: 3,
};

describe("LocalVad", () => {
  it("rejects silence and starts only after consecutive voiced frames", () => {
    const vad = new LocalVad(testOptions);
    expect(vad.process(0.001, false).speechStart).toBe(false);
    expect(vad.process(0.04, false).speechStart).toBe(false);
    expect(vad.process(0.04, false).speechStart).toBe(true);
  });

  it("commits only after minimum speech and bounded trailing silence", () => {
    const vad = new LocalVad(testOptions);
    vad.process(0.04, false);
    vad.process(0.04, false);
    vad.process(0.04, false);
    expect(vad.process(0, false).speechCommit).toBe(false);
    expect(vad.process(0, false).speechCommit).toBe(false);
    expect(vad.process(0, false).speechCommit).toBe(true);
  });

  it("uses the stricter speaker threshold and signals local barge-in", () => {
    const vad = new LocalVad(testOptions);
    expect(vad.process(0.05, true).bargeIn).toBe(false);
    expect(vad.process(0.05, true).bargeIn).toBe(false);
    expect(vad.process(0.1, true).bargeIn).toBe(false);
    const decision = vad.process(0.1, true);
    expect(decision.bargeIn).toBe(true);
    expect(decision.speechStart).toBe(true);
  });
});
