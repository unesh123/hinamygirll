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

  it("renders the main stage with brand and status", () => {
    render(<App />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getAllByText("HINAA").length).toBeGreaterThan(0);
    expect(document.querySelector(".header-status")).toHaveTextContent("Ready");
  });

  it("offers clear welcome actions without automatically starting a live session", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue work" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Talk to HINAA" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Start Live Session/i })).not.toBeInTheDocument();
  });

  it("shows the text composer as the dependable input path", () => {
    render(<App />);
    expect(screen.getByLabelText("Message HINAA")).toBeInTheDocument();
  });

  it("has settings trigger accessible", () => {
    render(<App />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("keeps the local voice control accessible in the composer", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: "Mute Hinaa voice" })).toBeInTheDocument();
  });

  it("opens the visible VSeeFace and VMC control panel from the avatar pill", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Open VSeeFace and VMC connection controls" }));
    expect(await screen.findByRole("dialog", { name: "VSeeFace and VMC connection panel" })).toBeInTheDocument();
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
    expect(screen.getByText(/Connect HINAA to its local VMC bridge/i)).toBeInTheDocument();
  });

  it("persists the selected approved avatar model across a remount", () => {
    const firstMount = render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Hinaa Classic" }));
    expect(localStorage.getItem("hinaa.avatar-model")).toBe("/models/model_5447.vrm");
    firstMount.unmount();

    render(<App />);
    expect(screen.getByRole("button", { name: "Hinaa Classic" })).toHaveClass("vrm-pill--active");
    expect(screen.getByRole("button", { name: "Hinaa" })).not.toHaveClass("vrm-pill--active");
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

    const composer = screen.getByLabelText("Message HINAA");
    fireEvent.change(composer, { target: { value: "Give me a quick status update." } });
    fireEvent.keyDown(composer, { key: "Enter" });

    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1), { timeout: 6_000 });
    const utterance = speak.mock.calls[0][0] as FakeUtterance;
    expect(utterance.text).toBeTruthy();
    expect(utterance.text).not.toContain("```");
    expect(screen.getByText("Speaking with local browser voice")).toBeInTheDocument();
    utterance.onend?.();
  });

  it.todo("starts live voice only after the user grants microphone permission");
  it.todo("offers a visible confirmation before executing an external assistant action");
});
