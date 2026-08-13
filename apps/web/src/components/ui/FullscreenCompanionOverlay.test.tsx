import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { TranscriptMessage } from "../../features/companion/types";
import { FullscreenCompanionOverlay } from "./FullscreenCompanionOverlay";

const messages: TranscriptMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    text: "Hello Unesh. I am ready whenever you are.",
    createdAt: "2026-08-13T10:00:00.000Z",
  },
  {
    id: "user-request",
    role: "user",
    text: "Help me plan my local image workflow.",
    createdAt: "2026-08-13T10:01:00.000Z",
  },
];

function renderOverlay(overrides: Partial<React.ComponentProps<typeof FullscreenCompanionOverlay>> = {}) {
  const actions = {
    onStartLive: vi.fn(),
    onStopLive: vi.fn(),
    onPauseLive: vi.fn(),
    onResumeLive: vi.fn(),
  };
  render(
    <FullscreenCompanionOverlay
      open
      companionName="HINAA"
      companionState="idle"
      live={{ active: false, paused: false, detail: "Voice is ready on this device.", microphoneLevel: 0 }}
      messages={messages}
      {...actions}
      {...overrides}
    />,
  );
  return actions;
}

describe("FullscreenCompanionOverlay", () => {
  it("offers an explicit microphone start control and shows durable conversation cards", () => {
    const actions = renderOverlay();

    expect(screen.getByRole("button", { name: "Start live conversation" })).toBeInTheDocument();
    expect(screen.getByText("Voice is ready on this device.")).toBeInTheDocument();
    expect(screen.getByText("Hello Unesh. I am ready whenever you are.")).toBeInTheDocument();
    expect(screen.getByText("Help me plan my local image workflow.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start live conversation" }));
    expect(actions.onStartLive).toHaveBeenCalledTimes(1);
  });

  it("uses the shared live-session controls and labels for an active paused session", () => {
    const actions = renderOverlay({
      companionState: "listening",
      live: { active: true, paused: true, detail: "Listening paused. Microphone tracks remain until Stop.", microphoneLevel: 0.65 },
    });

    expect(screen.getByText("Live conversation paused")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resume live conversation" }));
    fireEvent.click(screen.getByRole("button", { name: "Stop live conversation" }));

    expect(actions.onResumeLive).toHaveBeenCalledTimes(1);
    expect(actions.onStopLive).toHaveBeenCalledTimes(1);
  });

  it("keeps the microphone actionable after an unavailable-device recovery state", () => {
    renderOverlay({
      companionState: "error",
      live: { active: false, paused: false, detail: "Microphone permission denied · text mode still works", microphoneLevel: 0 },
    });

    expect(screen.getByText("Microphone permission denied · text mode still works")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start live conversation" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop live conversation" })).not.toBeInTheDocument();
  });

  it("presents partial user speech and streamed assistant text inside the stage", () => {
    renderOverlay({
      companionState: "speaking",
      live: { active: true, paused: false, detail: "Assistant audio is playing.", microphoneLevel: 0.25 },
      partialTranscript: "Can you explain how local voice works?",
      streamingText: "I will keep the answer concise and show the deeper details in chat.",
    });

    expect(screen.getByText("You are speaking")).toBeInTheDocument();
    expect(screen.getByText("Can you explain how local voice works?")).toBeInTheDocument();
    expect(screen.getByText("HINAA is replying")).toBeInTheDocument();
    expect(screen.getByText("I will keep the answer concise and show the deeper details in chat.")).toBeInTheDocument();
  });
});
