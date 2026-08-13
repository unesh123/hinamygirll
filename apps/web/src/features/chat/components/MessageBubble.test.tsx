import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TranscriptMessage } from "../../companion/types";
import { MessageBubble } from "./MessageBubble";

const message: TranscriptMessage = {
  id: "assistant-empty-tools",
  role: "assistant",
  text: "A complete assistant answer.",
  createdAt: "2026-08-12T12:00:00.000Z",
  plan: {
    displayText: "A complete assistant answer.",
    spokenText: "A concise answer.",
    language: "en-US",
    emotion: { primary: "neutral", intensity: 0.2, valence: 0.1, arousal: 0.1 },
    performance: { facePreset: "neutral", gesture: "none", gazeTarget: "camera", headMotion: "none", blinkRate: 0.4 },
    memoryCandidates: [],
    toolRequests: [],
  },
};

describe("MessageBubble", () => {
  it("does not render a numeric zero for an empty assistant tool-request list", () => {
    render(<MessageBubble message={message} onResolveTool={() => undefined} />);
    expect(screen.getByText("A complete assistant answer.")).toBeInTheDocument();
    expect(screen.queryByText("0", { exact: true })).not.toBeInTheDocument();
  });
});


  it("renders only the latest result when a persisted tool result is duplicated", () => {
    const duplicateResultMessage: TranscriptMessage = {
      ...message,
      id: "assistant-duplicate-tool-result",
      toolResults: [
        { toolName: "image_search", result: { status: "error", error: "Old image provider error" } },
        { toolName: "image_search", result: { status: "error", error: "Latest image provider error" } },
      ],
    };

    render(<MessageBubble message={duplicateResultMessage} onResolveTool={() => undefined} />);
    expect(screen.getByText("Latest image provider error")).toBeInTheDocument();
    expect(screen.queryByText("Old image provider error")).not.toBeInTheDocument();
    expect(screen.getAllByLabelText("Image search availability")).toHaveLength(1);
  });
