import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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

describe("HINAA assistant workspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.removeItem("hinaa.avatar-model");
    localStorage.removeItem("hinaa_settings_v1");
  });

  it("renders the Sakura OS navigation rail", () => {
    render(<App />);
    // NavigationRail should be present with aria-label
    expect(screen.getByLabelText("HINAA navigation")).toBeInTheDocument();
  });

  it("renders Talk, Work, and Operate mode buttons", () => {
    render(<App />);
    // Mode tabs in the header
    const talkBtn = screen.getAllByRole("button").find(el => /talk/i.test(el.textContent ?? ""));
    const workBtn = screen.getAllByRole("button").find(el => /work/i.test(el.textContent ?? ""));
    const operateBtn = screen.getAllByRole("button").find(el => /operate/i.test(el.textContent ?? ""));
    expect(talkBtn).toBeDefined();
    expect(workBtn).toBeDefined();
    expect(operateBtn).toBeDefined();
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
      _version: 2,
      appearance: { theme: "system", motion: "system", avatarVisible: true, avatarStyle: "procedural" },
      provider: { preferredMode: "mock", preferredModelByProvider: {} },
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
  });

  it.todo("starts live voice only after the user grants microphone permission");
  it.todo("offers a visible confirmation before executing an external assistant action");
});
