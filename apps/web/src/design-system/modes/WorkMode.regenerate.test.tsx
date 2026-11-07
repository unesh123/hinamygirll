import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkMode } from "./WorkMode";
import type { TranscriptMessage } from "../../features/companion/types";

const at = new Date().toISOString();
const conversation: TranscriptMessage[] = [
  { id: "a0", role: "assistant", text: "Namaste! K cha?", createdAt: at },
  { id: "u1", role: "user", text: "Explain recursion", createdAt: at },
  { id: "a1", role: "assistant", text: "Recursion is a function calling itself.", createdAt: at },
  { id: "u2", role: "user", text: "Give an example", createdAt: at },
  { id: "a2", role: "assistant", text: "Factorial is the classic one.", createdAt: at },
];

function renderWork(overrides: Partial<Parameters<typeof WorkMode>[0]> = {}) {
  const props: Parameters<typeof WorkMode>[0] = {
    companionState: "idle",
    messages: conversation,
    streamingText: "",
    partialTranscript: "",
    isThinking: false,
    input: "",
    onInputChange: vi.fn(),
    onSend: vi.fn(),
    onStop: vi.fn(),
    disabled: false,
    isVoiceActive: false,
    onStartVoice: vi.fn(),
    onStopVoice: vi.fn(),
    voiceFeedback: { kind: "idle", label: "" },
    powerUps: [],
    onPowerUpToggle: vi.fn(),
    onResolveTool: vi.fn(),
    autoRunTools: false,
    agentSteps: [],
    onWelcomeAction: vi.fn(),
    attachedImage: null,
    onImageAttach: vi.fn(),
    onRegenerate: vi.fn(),
    onEditMessage: vi.fn(),
    ...overrides,
  };
  const view = render(<WorkMode {...props} />);
  return { props, ...view };
}

describe("regenerate and edit", () => {
  it("offers regenerate only on the latest answer and calls it", () => {
    const { props } = renderWork();
    const buttons = screen.getAllByRole("button", { name: "Regenerate response" });
    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]);
    expect(props.onRegenerate).toHaveBeenCalledTimes(1);
  });

  it("hides regenerate while she is still answering", () => {
    renderWork({ isThinking: true });
    expect(screen.queryByRole("button", { name: "Regenerate response" })).not.toBeInTheDocument();
  });

  it("hides regenerate when there is nothing to re-answer", () => {
    renderWork({ messages: [conversation[0]] });
    expect(screen.queryByRole("button", { name: "Regenerate response" })).not.toBeInTheDocument();
  });

  it("calls the latest handler after the parent re-renders", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { props, rerender } = renderWork({ onRegenerate: first });
    rerender(<WorkMode {...props} onRegenerate={second} />);
    fireEvent.click(screen.getByRole("button", { name: "Regenerate response" }));
    expect(second).toHaveBeenCalledTimes(1);
    expect(first).not.toHaveBeenCalled();
  });

  it("edits a user message in place and resends it", () => {
    const { props } = renderWork();
    fireEvent.click(screen.getAllByRole("button", { name: "Edit message" })[0]);
    const box = screen.getByRole("textbox", { name: "Edit message" });
    expect(box).toHaveValue("Explain recursion");
    fireEvent.change(box, { target: { value: "Explain recursion in Nepali" } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(props.onEditMessage).toHaveBeenCalledWith("u1", "Explain recursion in Nepali");
    expect(screen.queryByRole("textbox", { name: "Edit message" })).not.toBeInTheDocument();
  });

  it("cancels an edit with Escape and does not resend unchanged text", () => {
    const { props } = renderWork();
    fireEvent.click(screen.getAllByRole("button", { name: "Edit message" })[1]);
    const box = screen.getByRole("textbox", { name: "Edit message" });
    fireEvent.keyDown(box, { key: "Escape" });
    expect(screen.queryByRole("textbox", { name: "Edit message" })).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Edit message" })[1]);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(props.onEditMessage).not.toHaveBeenCalled();
  });

  it("shows no edit control without an edit handler", () => {
    renderWork({ onEditMessage: undefined });
    expect(screen.queryByRole("button", { name: "Edit message" })).not.toBeInTheDocument();
  });
});
