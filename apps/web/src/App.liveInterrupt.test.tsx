import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Typed barge-in during a live voice session ──
// Regression: the submit handler used to `return` early whenever live voice
// was active, so a message typed while HINAA was mid-reply vanished and her
// previous answer played to the end over the top of it.

const interruptSpeech = vi.fn();
const liveStart = vi.fn();
const liveStop = vi.fn();

const liveDiagnostics = {
  micPermission: "granted",
  trackState: "live",
  audioContextState: "running",
  inputSampleRate: 48000,
  rmsLevel: 0,
  chunksSentPerSecond: 0,
  sttSocketState: "open",
  lastPartialTranscript: "",
  lastCommittedTranscript: "",
  sttLatencyMs: 0,
  brainProvider: "mock",
  firstTokenReceived: true,
  brainLatencyMs: 0,
  ttsProvider: "mock",
  ttsSocketState: "open",
  audioChunksReceived: 0,
  playbackState: "playing",
  currentStage: "playing",
  lastError: "",
  turnCount: 1,
  activeTurnId: "turn-1",
  queueEncodedChunks: 0,
  queueDecoding: 0,
  queueDecodedBuffers: 0,
  queueScheduledSources: 1,
  queueDrained: false,
  finalSequenceReceived: false,
  voiceRoute: {
    sttProvider: "mock",
    sttTransport: "ws",
    brainProvider: "mock",
    brainModel: "mock",
    ttsProvider: "mock",
    ttsTransport: "ws",
    ttsVoiceId: "mock",
  },
};

vi.mock("./features/audio/useLiveConversation", () => ({
  useLiveConversation: () => ({
    active: true,
    status: "listening",
    detail: "Speaking",
    microphoneLevel: 0,
    metrics: {},
    voiceMetadata: undefined,
    paused: false,
    diagnostics: liveDiagnostics,
    manualCommit: vi.fn(),
    interruptSpeech,
    startPushToTalk: vi.fn(),
    stopPushToTalk: vi.fn(),
    start: liveStart,
    pause: vi.fn(),
    resume: vi.fn(),
    stop: liveStop,
  }),
}));

import App from "./App";

function resetHinaaStorage(): void {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("hinaa")) localStorage.removeItem(key);
  }
}

describe("typed barge-in while live voice is active", () => {
  beforeEach(() => {
    resetHinaaStorage();
    interruptSpeech.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    resetHinaaStorage();
  });

  it("stops her current speech and still sends the message", async () => {
    render(<App />);
    const composer = screen.getByPlaceholderText("Ask HINA anything — chat mode...");

    fireEvent.change(composer, { target: { value: "stop and answer this" } });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: false });

    // Her in-flight voice reply is interrupted instead of playing over the
    // new message, and the message itself is not swallowed by the live guard.
    expect(interruptSpeech).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("stop and answer this")).toBeInTheDocument();
  });
});
