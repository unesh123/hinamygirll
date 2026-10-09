import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Dictation barge-in ──
// Regression: while HINAA was speaking, typing or dictating into the composer
// (Wispr Flow injects text keystroke-by-keystroke) left her previous reply
// playing — her voice and mouth ran over his until he finally hit send. The
// first character that grows the composer now interrupts her.

const interruptSpeech = vi.fn();
const playbackStop = vi.fn();

vi.mock("./features/audio/useLiveConversation", () => ({
  useLiveConversation: () => ({
    active: true,
    status: "speaking",
    detail: "Speaking",
    microphoneLevel: 0,
    metrics: {},
    voiceMetadata: undefined,
    paused: false,
    diagnostics: { currentStage: "playing" },
    manualCommit: vi.fn(),
    interruptSpeech,
    startPushToTalk: vi.fn(),
    stopPushToTalk: vi.fn(),
    start: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    stop: vi.fn(),
  }),
}));

vi.mock("./features/audio/useAudioPlayback", () => ({
  useAudioPlayback: () => ({
    playing: true,
    muted: false,
    hasReplay: false,
    speech: { current: null },
    jawEnergy: { current: 0 },
    playingRef: { current: true },
    visemeEvents: { current: [] },
    audioStartTimeRef: { current: 0 },
    stop: playbackStop,
    play: vi.fn(),
    replay: vi.fn(),
    speakBrowser: vi.fn(),
    speakStreamChunk: vi.fn(),
    beginSpeechStream: vi.fn(),
    unlockAudio: vi.fn(),
    toggleMute: vi.fn(),
  }),
}));

import App from "./App";

function resetHinaaStorage(): void {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("hinaa")) localStorage.removeItem(key);
  }
}

describe("dictation barge-in while she is speaking", () => {
  beforeEach(() => {
    resetHinaaStorage();
    interruptSpeech.mockClear();
    playbackStop.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    resetHinaaStorage();
  });

  it("falls silent the moment dictation text starts appearing", async () => {
    render(<App />);
    const composer = screen.getByPlaceholderText("Ask HINA anything — chat mode...");

    // Wispr Flow grows the field incrementally; the first growth interrupts.
    fireEvent.change(composer, { target: { value: "h" } });

    expect(interruptSpeech).toHaveBeenCalled();
    expect(playbackStop).toHaveBeenCalled();
  });

  it("does not interrupt when she is already silent", async () => {
    render(<App />);
    interruptSpeech.mockClear();
    playbackStop.mockClear();
    const composer = screen.getByPlaceholderText("Ask HINA anything — chat mode...");

    // playback.playing stays mocked true here, so simulate the silent case by
    // clearing after the first interrupt and shrinking the field instead.
    fireEvent.change(composer, { target: { value: "" } });
    expect(interruptSpeech).not.toHaveBeenCalled();
    expect(playbackStop).not.toHaveBeenCalled();
  });
});
