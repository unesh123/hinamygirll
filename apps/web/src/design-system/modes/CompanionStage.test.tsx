import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CompanionStage, type CompanionStageProps } from "./CompanionStage";

vi.mock("../../features/avatar/LazyAvatarPresence", () => ({
  LazyAvatarPresence: (props: { mode: string; state: string }) => (
    <div data-testid="avatar" data-mode={props.mode} data-state={props.state} />
  ),
}));
vi.mock("../hud", async (orig) => ({ ...(await orig<object>()), ParticleField: () => null }));

function setup(over: Partial<CompanionStageProps> = {}) {
  const props: CompanionStageProps = {
    companionState: "idle",
    messages: [],
    isVoiceActive: false,
    visionEnabled: false,
    onStartVoice: vi.fn(),
    onStopVoice: vi.fn(),
    onToggleVision: vi.fn(),
    onOpenMemory: vi.fn(),
    onOpenWorkspace: vi.fn(),
    onSendText: vi.fn(),
    ...over,
  };
  render(<CompanionStage {...props} />);
  return props;
}

const reply = (text: string) => ({ id: "m1", role: "assistant" as const, text, createdAt: "2026-01-01T00:00:00Z" });

describe("CompanionStage", () => {
  it("renders the avatar, state, and no subtitle when silent", () => {
    setup();
    expect(screen.getByTestId("companion-stage")).toBeInTheDocument();
    expect(screen.getByTestId("avatar")).toHaveAttribute("data-state", "idle");
    expect(screen.getByRole("status")).toHaveTextContent("Here with you");
    expect(screen.queryByTestId("companion-subtitle")).not.toBeInTheDocument();
  });

  it("shows live streaming text over the last reply, plus what she heard", () => {
    setup({ messages: [reply("Old reply")], streamingText: "Hello **there**", partialTranscript: "hi hina", companionState: "speaking" });
    const sub = screen.getByTestId("companion-subtitle");
    expect(sub).toHaveTextContent("Hello there");
    expect(sub).not.toHaveTextContent("Old reply");
    expect(sub).toHaveTextContent("You: hi hina");
  });

  it("falls back to her latest reply", () => {
    setup({ messages: [reply("Welcome back")] });
    expect(screen.getByTestId("companion-subtitle")).toHaveTextContent("Welcome back");
  });

  it("sends trimmed text from the composer and clears it", async () => {
    const { onSendText } = setup();
    const input = screen.getByRole("textbox", { name: /message/i });
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    await userEvent.type(input, "  good morning  ");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(onSendText).toHaveBeenCalledWith("good morning");
    expect(input).toHaveValue("");
  });

  it("does not send blank input on Enter", () => {
    const { onSendText } = setup();
    fireEvent.submit(screen.getByRole("textbox", { name: /message/i }).closest("form")!);
    expect(onSendText).not.toHaveBeenCalled();
  });

  it("quick chips trigger their commands", async () => {
    const p = setup();
    await userEvent.click(screen.getByRole("button", { name: "Talk" }));
    expect(p.onStartVoice).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Camera awareness/ }));
    expect(p.onToggleVision).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Memory" }));
    expect(p.onOpenMemory).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Workspace" }));
    expect(p.onOpenWorkspace).toHaveBeenCalled();
  });

  it("stops voice when already live and reflects camera state", async () => {
    const p = setup({ isVoiceActive: true, visionEnabled: true });
    expect(screen.getByRole("button", { name: /Camera awareness/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Stop talking" }));
    expect(p.onStopVoice).toHaveBeenCalled();
    expect(p.onStartVoice).not.toHaveBeenCalled();
  });

  it("shows the mood from the turn plan", () => {
    setup({ plan: { emotion: { primary: "shy" } } as never });
    expect(screen.getByTestId("companion-mood")).toHaveTextContent("shy");
  });
});
