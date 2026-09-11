import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ModelControlBar, IMAGE_ENGINES, VOICE_ENGINES, getStoredModelPrefs, saveModelPrefs, STORAGE_KEY_MODEL_PREFS } from "./ModelControlBar";
import type { ModelControlBarProps } from "./ModelControlBar";

const baseProps: ModelControlBarProps = {
  currentMode: "auto",
  currentModel: null,
  providerOptions: [
    { mode: "auto", label: "Auto", description: "Best available provider", health: "healthy", available: true },
    { mode: "claude", label: "Claude", description: "Anthropic Claude", health: "healthy", available: true },
    { mode: "gemini", label: "Gemini", description: "Google Gemini", health: "healthy", available: true },
  ],
  getModelOptions: () => [],
  onSelectProvider: vi.fn(),
  imageEngine: "auto",
  onSelectImageEngine: vi.fn(),
  voiceEngine: "auto",
  onSelectVoiceEngine: vi.fn(),
};

describe("ModelControlBar", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("renders three selector buttons", () => {
    render(<ModelControlBar {...baseProps} />);
    expect(screen.getByTestId("brain-selector-btn")).toBeInTheDocument();
    expect(screen.getByTestId("image-selector-btn")).toBeInTheDocument();
    expect(screen.getByTestId("voice-selector-btn")).toBeInTheDocument();
  });

  it("shows brain dropdown when brain button is clicked", () => {
    render(<ModelControlBar {...baseProps} />);
    const brainBtn = screen.getByTestId("brain-selector-btn");
    fireEvent.click(brainBtn);
    expect(screen.getByTestId("brain-dropdown")).toBeInTheDocument();
  });

  it("shows image engine dropdown when image button is clicked", () => {
    render(<ModelControlBar {...baseProps} />);
    const imageBtn = screen.getByTestId("image-selector-btn");
    fireEvent.click(imageBtn);
    expect(screen.getByTestId("image-dropdown")).toBeInTheDocument();
    // Each engine option must be present by testid (label includes emoji prefix)
    IMAGE_ENGINES.forEach((e) => {
      expect(screen.getByTestId(`image-option-${e.id}`)).toBeInTheDocument();
    });
  });

  it("shows voice engine dropdown when voice button is clicked", () => {
    render(<ModelControlBar {...baseProps} />);
    const voiceBtn = screen.getByTestId("voice-selector-btn");
    fireEvent.click(voiceBtn);
    expect(screen.getByTestId("voice-dropdown")).toBeInTheDocument();
    VOICE_ENGINES.forEach((e) => {
      expect(screen.getByTestId(`voice-option-${e.id}`)).toBeInTheDocument();
    });
  });

  it("calls onSelectImageEngine when an image engine is selected", () => {
    const onSelectImageEngine = vi.fn();
    render(<ModelControlBar {...baseProps} onSelectImageEngine={onSelectImageEngine} />);
    fireEvent.click(screen.getByTestId("image-selector-btn"));
    // Use testid instead of text since labels include emoji icons
    fireEvent.click(screen.getByTestId("image-option-gemini-3.1-flash-image"));
    expect(onSelectImageEngine).toHaveBeenCalledWith("gemini-3.1-flash-image");
  });

  it("calls onSelectVoiceEngine when a voice engine is selected", () => {
    const onSelectVoiceEngine = vi.fn();
    render(<ModelControlBar {...baseProps} onSelectVoiceEngine={onSelectVoiceEngine} />);
    fireEvent.click(screen.getByTestId("voice-selector-btn"));
    fireEvent.click(screen.getByTestId("voice-option-azure-speech"));
    expect(onSelectVoiceEngine).toHaveBeenCalledWith("azure-speech");
  });

  it("displays the active image engine label in the button", () => {
    render(<ModelControlBar {...baseProps} imageEngine="gemini-3-pro-image" />);
    // Label text is "Gemini 3 Pro" (may be combined with emoji in DOM)
    const btn = screen.getByTestId("image-selector-btn");
    expect(btn.textContent).toContain("Gemini 3 Pro");
  });

  it("displays the active voice engine label in the button", () => {
    render(<ModelControlBar {...baseProps} voiceEngine="azure-speech" />);
    const btn = screen.getByTestId("voice-selector-btn");
    expect(btn.textContent).toContain("Azure Neural");
  });

  it("closes dropdown when clicking outside", () => {
    render(
      <div>
        <ModelControlBar {...baseProps} />
        <div data-testid="outside">outside</div>
      </div>
    );
    fireEvent.click(screen.getByTestId("brain-selector-btn"));
    expect(screen.getByTestId("brain-dropdown")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByTestId("brain-dropdown")).not.toBeInTheDocument();
  });
});

describe("ModelControlBar localStorage utilities", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("getStoredModelPrefs returns defaults when localStorage is empty", () => {
    const prefs = getStoredModelPrefs();
    expect(prefs.brainMode).toBe("auto");
    expect(prefs.imageEngine).toBe("auto");
    expect(prefs.voiceEngine).toBe("auto");
    expect(prefs.brainModel).toBeNull();
  });

  it("saveModelPrefs persists values to localStorage", () => {
    saveModelPrefs({ imageEngine: "gemini-3-pro-image", voiceEngine: "azure-speech" });
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY_MODEL_PREFS) || "{}");
    expect(stored.imageEngine).toBe("gemini-3-pro-image");
    expect(stored.voiceEngine).toBe("azure-speech");
  });

  it("getStoredModelPrefs reads persisted values after save", () => {
    saveModelPrefs({ brainMode: "claude", imageEngine: "comfyui", voiceEngine: "gemini-live" });
    const prefs = getStoredModelPrefs();
    expect(prefs.brainMode).toBe("claude");
    expect(prefs.imageEngine).toBe("comfyui");
    expect(prefs.voiceEngine).toBe("gemini-live");
  });

  it("saveModelPrefs merges with existing prefs (partial update)", () => {
    saveModelPrefs({ imageEngine: "comfyui", voiceEngine: "auto", brainMode: "auto" });
    saveModelPrefs({ voiceEngine: "azure-speech" }); // Only update voiceEngine
    const prefs = getStoredModelPrefs();
    expect(prefs.imageEngine).toBe("comfyui"); // Unchanged
    expect(prefs.voiceEngine).toBe("azure-speech"); // Updated
  });
});
