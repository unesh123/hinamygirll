import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

class FakeUtterance {
  lang = "";
  rate = 1;
  pitch = 1;
  volume = 1;
  voice: SpeechSynthesisVoice | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly text: string) {}
}

function resetHinaaStorage(): void {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("hinaa")) localStorage.removeItem(key);
  }
}

describe("HINAA assistant workspace", () => {
  beforeEach(() => {
    resetHinaaStorage();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    resetHinaaStorage();
  });

  it("renders the Sakura OS navigation rail", () => {
    render(<App />);
    expect(screen.getByLabelText("HINAA navigation")).toBeInTheDocument();
  });

  it("renders Talk, Chat, and Projects navigation destinations", () => {
    render(<App />);
    expect(screen.getAllByRole("button", { name: "Talk" })[0]).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Chat" })[0]).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Projects" })[0]).toBeInTheDocument();
  });

  it("shows the Work mode text composer", () => {
    render(<App />);
    const composer = screen.getByPlaceholderText("Ask HINAA anything...");
    expect(composer).toBeInTheDocument();
  });

  it("shows welcome actions in Work mode", () => {
    render(<App />);
    // Welcome cards should be visible in Work mode
    const research = screen.getAllByRole("button").find(el => el.textContent?.includes("Research"));
    const create = screen.getAllByRole("button").find(el => el.textContent?.includes("Create"));
    expect(research).toBeDefined();
    expect(create).toBeDefined();
  });

  it("system errors do not appear in the conversation", () => {
    render(<App />);
    expect(screen.queryByText(/safety limit/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/microphone frame was lost/i)).not.toBeInTheDocument();
  });

  it("speaks one concise spokenText utterance for a completed typed Demo turn", async () => {
    const speak = vi.fn();
    vi.stubGlobal("speechSynthesis", { getVoices: () => [], speak, cancel: vi.fn() });
    vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
    vi.stubGlobal("AudioContext", undefined);
    localStorage.setItem("hinaa_settings_v1", JSON.stringify({
      _version: 7,
      appearance: { theme: "system", motion: "system", avatarVisible: true, avatarStyle: "procedural" },
      provider: { preferredMode: "mock", preferredModelByProvider: {} },
      language: { activePolicy: "en-US" },
      automation: { autoRunTools: false },
    }));
    render(<App />);

    const composer = screen.getByPlaceholderText("Ask HINAA anything...");
    fireEvent.change(composer, { target: { value: "Give me a quick status update." } });
    fireEvent.keyDown(composer, { key: "Enter" });

    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1), { timeout: 6_000 });
    const utterance = speak.mock.calls[0][0] as FakeUtterance;
    expect(utterance.text).toBeTruthy();
    expect(utterance.text).not.toContain("```");
    utterance.onend?.();
  }, 10_000);

  it.todo("starts live voice only after the user grants microphone permission");
  it.todo("offers a visible confirmation before executing an external assistant action");
});
