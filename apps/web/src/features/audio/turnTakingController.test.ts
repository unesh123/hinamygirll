import { describe, expect, it } from "vitest";
import { TurnTakingController } from "./turnTakingController";

function runFrames(
  controller: TurnTakingController,
  levels: number[],
  partial = "Namaste project progress clear cha",
  extras: Partial<{
    assistantPlaying: boolean;
    paused: boolean;
    sessionActive: boolean;
  }> = {},
) {
  const decisions = [];
  for (const level of levels) {
    decisions.push(
      controller.process({
        level,
        assistantPlaying: extras.assistantPlaying ?? false,
        partialText: partial,
        sessionActive: extras.sessionActive ?? true,
        paused: extras.paused ?? false,
      }),
    );
  }
  return decisions;
}

describe("TurnTakingController", () => {
  it("commits one short English sentence after silence", () => {
    const controller = new TurnTakingController({
      startFrames: 2,
      minimumSpeechFrames: 3,
      hesitationFrames: 2,
      endOfTurnFrames: 4,
      maxSilenceFrames: 6,
    });
    const decisions = runFrames(
      controller,
      [...Array(6).fill(0.08), ...Array(5).fill(0.001)],
      "Hello Hinaa how are you",
    );
    expect(decisions.some((d) => d.speechCommit)).toBe(true);
  });

  it("handles long Nepali Devanagari sentence", () => {
    const controller = new TurnTakingController({
      startFrames: 2,
      minimumSpeechFrames: 3,
      endOfTurnFrames: 4,
      maxSilenceFrames: 6,
      hesitationFrames: 2,
    });
    const partial = "आज म लाइभ भ्वाइस परीक्षण गर्दै छु र छोटो जवाफ चाहन्छु";
    const decisions = runFrames(
      controller,
      [...Array(6).fill(0.09), ...Array(5).fill(0)],
      partial,
    );
    expect(decisions.some((d) => d.speechCommit)).toBe(true);
  });

  it("handles Romanized Nepali and Hindi and mixed sentences", () => {
    for (const partial of [
      "Ma aile timisanga live voice test gardai chu",
      "Main beech mein bolun to immediately ruk jana",
      "Yo bug TypeError ho tara stack clear cha",
      "Memory consent naturally samjha do in Hindi and English",
    ]) {
      const controller = new TurnTakingController({
        startFrames: 2,
        minimumSpeechFrames: 3,
        endOfTurnFrames: 3,
        maxSilenceFrames: 5,
        hesitationFrames: 1,
      });
      const decisions = runFrames(
        controller,
        [...Array(5).fill(0.1), ...Array(4).fill(0)],
        partial,
      );
      expect(decisions.some((d) => d.speechCommit)).toBe(true);
    }
  });

  it("treats short silence as hesitation, not end of turn", () => {
    const controller = new TurnTakingController({
      startFrames: 2,
      minimumSpeechFrames: 3,
      hesitationFrames: 4,
      endOfTurnFrames: 10,
      maxSilenceFrames: 12,
    });
    const decisions = runFrames(
      controller,
      [0.08, 0.08, 0.08, 0.08, 0.001, 0.001, 0.08, 0.08],
    );
    expect(decisions.some((d) => d.state === "hesitation")).toBe(true);
    expect(decisions.some((d) => d.speechCommit)).toBe(false);
  });

  it("supports multiple mid-sentence pauses without early commit", () => {
    const controller = new TurnTakingController({
      startFrames: 2,
      minimumSpeechFrames: 4,
      hesitationFrames: 3,
      endOfTurnFrames: 8,
      maxSilenceFrames: 12,
    });
    const decisions = runFrames(
      controller,
      [0.1, 0.1, 0.1, 0.0, 0.0, 0.1, 0.1, 0.0, 0.0, 0.1, 0.1, 0.1],
      "please explain memory consent",
    );
    expect(decisions.filter((d) => d.speechCommit).length).toBe(0);
  });

  it("does not commit empty or noise-only energy without transcript", () => {
    const controller = new TurnTakingController({
      startFrames: 2,
      minimumSpeechFrames: 2,
      endOfTurnFrames: 2,
      maxSilenceFrames: 2,
      hesitationFrames: 0,
      minimumTranscriptChars: 3,
    });
    const empty = runFrames(controller, [0.2, 0.2, 0.0, 0.0], "  ");
    expect(empty.some((d) => d.speechCommit)).toBe(false);
  });

  it("suppresses duplicate commits with the same fingerprint", () => {
    const controller = new TurnTakingController({
      startFrames: 1,
      minimumSpeechFrames: 1,
      endOfTurnFrames: 1,
      maxSilenceFrames: 1,
      hesitationFrames: 0,
    });
    const first = runFrames(controller, [0.1, 0.0], "hello world there");
    const second = runFrames(controller, [0.1, 0.0], "hello world there");
    expect(first.some((d) => d.speechCommit)).toBe(true);
    expect(second.some((d) => d.reason === "duplicate_commit_suppressed")).toBe(
      true,
    );
  });

  it("barge-in when assistant is playing and energy rises", () => {
    const controller = new TurnTakingController({ startFrames: 2 });
    // Barge-in is intentional: it requires sustained voice (bargeInFrames = 8
    // frames, ~160ms) so playback echo can never cut Hinaa off.
    const frames = [...Array(8).fill(0.2)];
    const decisions = frames.map(() =>
      controller.process({
        level: 0.2,
        assistantPlaying: true,
        partialText: "",
        sessionActive: true,
        paused: false,
      }),
    );
    expect(decisions.some((d) => d.bargeIn)).toBe(true);
    expect(decisions.at(-1)?.state).toBe("interrupted");
  });

  it("repeated barge-in stays interruptible", () => {
    const controller = new TurnTakingController({ startFrames: 1 });
    const run = () =>
      [...Array(8).fill(0.3)].map(() =>
        controller.process({
          level: 0.3,
          assistantPlaying: true,
          partialText: "x",
          sessionActive: true,
          paused: false,
        }),
      );
    const a = run();
    controller.resetSpeech();
    controller.setSessionState("speaking");
    const b = run();
    expect(a.some((d) => d.bargeIn) || b.some((d) => d.bargeIn)).toBe(true);
  });

  it("paused session never commits", () => {
    const controller = new TurnTakingController();
    const decision = controller.process({
      level: 0.5,
      assistantPlaying: false,
      partialText: "hello",
      sessionActive: true,
      paused: true,
    });
    expect(decision.speechCommit).toBe(false);
    expect(decision.reason).toBe("paused");
  });

  it("inactive session never commits", () => {
    const controller = new TurnTakingController();
    const decision = controller.process({
      level: 0.9,
      assistantPlaying: false,
      partialText: "hello there friend",
      sessionActive: false,
      paused: false,
    });
    expect(decision.state).toBe("inactive");
    expect(decision.speechCommit).toBe(false);
  });

  it("two rapid turns can commit sequentially with different text", () => {
    const controller = new TurnTakingController({
      startFrames: 1,
      minimumSpeechFrames: 1,
      endOfTurnFrames: 1,
      maxSilenceFrames: 1,
      hesitationFrames: 0,
    });
    const first = runFrames(controller, [0.2, 0], "first turn text here");
    controller.resetSpeech();
    const second = runFrames(controller, [0.2, 0], "second turn text here");
    expect(first.some((d) => d.speechCommit)).toBe(true);
    expect(second.some((d) => d.speechCommit)).toBe(true);
  });

  it("marks provider unavailable and reconnecting externally", () => {
    const controller = new TurnTakingController();
    controller.setSessionState("provider_unavailable");
    expect(controller.currentState).toBe("provider_unavailable");
    controller.setSessionState("reconnecting");
    expect(controller.currentState).toBe("reconnecting");
  });
});
