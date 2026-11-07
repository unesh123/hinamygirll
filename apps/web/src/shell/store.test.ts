import { beforeEach, describe, expect, it, vi } from "vitest";
import { MODE_STORAGE_KEY, registerAppCommands, runAppCommand, shell, getShellState } from "./store";

describe("shell store", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    shell.reset();
  });

  it("persists the mode switch and reads it back", () => {
    expect(getShellState().mode).toBe("workspace");
    shell.setMode("companion");
    expect(localStorage.getItem(MODE_STORAGE_KEY)).toBe("companion");
    shell.reset();
    expect(getShellState().mode).toBe("companion");
  });

  it("toggles the mode and reports the new one", () => {
    expect(shell.toggleMode()).toBe("companion");
    expect(shell.toggleMode()).toBe("workspace");
  });

  it("toggles the theme, applies it to the DOM and persists it in settings", () => {
    shell.setTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    shell.toggleTheme();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(getShellState().theme).toBe("light");
    expect(JSON.parse(localStorage.getItem("hinaa_settings_v1") ?? "{}").appearance.theme).toBe("light");
    shell.reset();
    expect(getShellState().theme).toBe("light");
  });

  it("runs host commands immediately when registered and queues them otherwise", async () => {
    const newChat = vi.fn();
    runAppCommand("new-chat");
    expect(newChat).not.toHaveBeenCalled();
    const off = registerAppCommands({ "new-chat": newChat });
    await Promise.resolve();
    expect(newChat).toHaveBeenCalledTimes(1);
    runAppCommand("new-chat");
    expect(newChat).toHaveBeenCalledTimes(2);
    off();
  });

  it("only publishes agent snapshots that changed", () => {
    const snapshot = { state: "idle" as const, level: 0, voiceActive: false, streamingText: "", lastText: null, steps: [], model: null };
    const before = getShellState().agent;
    shell.publishAgent({ ...snapshot });
    expect(getShellState().agent).toBe(before);
    shell.publishAgent({ ...snapshot, state: "thinking" });
    expect(getShellState().agent.state).toBe("thinking");
  });
});
