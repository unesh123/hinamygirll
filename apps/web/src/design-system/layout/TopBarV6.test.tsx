import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { TopBarV6 } from "./TopBarV6";
vi.mock("@clerk/react", () => ({ UserButton: () => null }));
vi.mock("../../features/providers/hooks/useCapabilities", () => ({ useCapabilities: () => ({ models: [], providers: [], runtime: { backendConnected: true }, loading: false, refetch: vi.fn() }) }));
afterEach(cleanup);
const base = { currentMode: "talk" as const, executiveMode: "chat" as const, onModeChange: vi.fn(), onExecutiveModeChange: vi.fn() };
describe("top bar voice menu", () => {
  it("escapes the clipped header and changes the selected voice", () => {
    const select = vi.fn();
    render(<TopBarV6 {...base} voiceEngine="auto" onSelectVoiceEngine={select} />);
    const trigger = screen.getByRole("button", { name: "Choose voice engine" });
    fireEvent.click(trigger);
    const menu = screen.getByRole("menu", { name: "Voice engines" });
    expect(menu.parentElement).toBe(document.body);
    expect(menu.style.position).toBe("fixed");
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    fireEvent.mouseDown(screen.getByTestId("topbar-voice-option-elevenlabs"));
    fireEvent.click(screen.getByTestId("topbar-voice-option-elevenlabs"));
    expect(select).toHaveBeenCalledWith("elevenlabs");
    expect(screen.queryByRole("menu", { name: "Voice engines" })).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
  it("supports keyboard movement and Escape", () => {
    render(<TopBarV6 {...base} />);
    const trigger = screen.getByRole("button", { name: "Choose voice engine" });
    fireEvent.click(trigger);
    expect(document.activeElement).toBe(screen.getByTestId("topbar-voice-option-elevenlabs"));
    fireEvent.keyDown(document.activeElement!, { key: "ArrowDown" });
    expect(document.activeElement).toBe(screen.getByTestId("topbar-voice-option-auto"));
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
