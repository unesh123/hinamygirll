import { describe, expect, it } from "vitest";
import { LatencyClock } from "./latencyClock";

describe("LatencyClock", () => {
  it("records monotonic milestones without fabricating values", () => {
    let t = 1000;
    const clock = new LatencyClock(() => {
      t += 5;
      return t;
    });
    clock.mark("live_session_started");
    clock.mark("microphone_ready");
    expect(clock.delta("live_session_started", "microphone_ready")).toBe(5);
    expect(clock.delta("speech_started", "stt_final")).toBeUndefined();
  });
});
