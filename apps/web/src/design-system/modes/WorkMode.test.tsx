import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkMode } from "./WorkMode";
import type { TranscriptMessage } from "../../features/companion/types";

const messages: TranscriptMessage[] = [
  {
    id: "m1",
    role: "assistant",
    text: "Hello Unesh.",
    timestamp: Date.now(),
  },
];

function defaultProps(): Parameters<typeof WorkMode>[0] {
  return {
    companionState: "idle",
    messages,
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
  };
}

function renderWorkMode(overrides: Partial<Parameters<typeof WorkMode>[0]> = {}) {
  const props: Parameters<typeof WorkMode>[0] = { ...defaultProps(), ...overrides };

  render(<WorkMode {...props} />);
  return props;
}

describe("WorkMode voice controls", () => {
  it("renders assistant markdown as a document and leaves user text literal", () => {
    renderWorkMode({ messages: [
      { id: "user", role: "user", text: "## keep this literal", createdAt: new Date().toISOString() },
      { id: "answer", role: "assistant", text: "## Haan bro 🌸\n\n- **Done**\n- Next step", createdAt: new Date().toISOString() },
    ] });
    expect(screen.getByRole("heading", { name: "Haan bro 🌸" })).toBeInTheDocument();
    expect(screen.getByText("Done").tagName).toBe("STRONG");
    expect(screen.getByText("## keep this literal")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message HINAA" })).toBeInTheDocument();
  });
  it("uses singular message grammar in the work header", () => {
    renderWorkMode();
    expect(screen.getByText(/1 message$/)).toBeInTheDocument();
  });

  it("stops an active backend live voice session from the Done banner", () => {
    const onStopVoice = vi.fn();
    const onStartVoice = vi.fn();
    renderWorkMode({ isVoiceActive: true, onStopVoice, onStartVoice });

    fireEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(onStopVoice).toHaveBeenCalledTimes(1);
    expect(onStartVoice).not.toHaveBeenCalled();
  });

  it("renders provider micro-status line with active mode, model, and latency", () => {
    renderWorkMode({
      activeProviderMode: "cx-gateway",
      activeProviderModel: "GPT-5.6 Sol",
      providerHealth: "healthy",
      providerLatencyMs: 480,
    });

    const statusLine = screen.getByTestId("provider-micro-status");
    expect(statusLine).toBeInTheDocument();
    expect(statusLine).toHaveTextContent("CX Gateway");
    expect(statusLine).toHaveTextContent("GPT-5.6 Sol");
    expect(statusLine).toHaveTextContent("Ready · 480ms");
  });

  it("renders fallback switch button when provider is unavailable", () => {
    const onSelectProvider = vi.fn();
    renderWorkMode({
      activeProviderMode: "cx-gateway",
      providerHealth: "unavailable",
      onSelectProvider,
    });

    const fallbackBtn = screen.getByRole("button", { name: /Switch to Gemini/i });
    expect(fallbackBtn).toBeInTheDocument();
    fireEvent.click(fallbackBtn);
    expect(onSelectProvider).toHaveBeenCalledWith("real", "gemini-2.5-flash");
  });

  it("renders rate limit recovery card when message contains rate limit error", () => {
    const onSelectProvider = vi.fn();
    const onRetry = vi.fn();
    const userMsg: TranscriptMessage = {
      id: "u-1",
      role: "user",
      text: "Write a high-frequency trading bot in Python",
      createdAt: new Date().toISOString(),
    };
    const rateLimitedMessage: TranscriptMessage = {
      id: "err-1",
      role: "assistant",
      text: "The selected brain model is temporarily rate limited. Please wait a moment or switch to Gemini.",
      createdAt: new Date().toISOString(),
    };

    renderWorkMode({
      messages: [userMsg, rateLimitedMessage],
      onSelectProvider,
      onRetry,
    });

    const recoveryCard = screen.getByTestId("rate-limit-recovery-card");
    expect(recoveryCard).toBeInTheDocument();
    expect(screen.getByText(/Brain Model Rate Limit \/ Cooldown Active/i)).toBeInTheDocument();

    const switchBtn = screen.getByRole("button", { name: /Switch to Gemini 2.5 Flash/i });
    fireEvent.click(switchBtn);
    expect(onSelectProvider).toHaveBeenCalledWith("real", "gemini-2.5-flash");

    const retryBtn = screen.getByRole("button", { name: /Retry Prompt/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders avatar model switcher in companion panel header and allows model selection", () => {
    const onSelectModel = vi.fn();
    renderWorkMode({
      avatarModel: "/models/5798998195377315936 (1).vrm",
      onSelectModel,
    });

    const companionPanel = screen.getByTestId("work-companion-panel");
    expect(companionPanel).toBeInTheDocument();

    const switchBtn = screen.getByRole("button", { name: /Switch 3D Avatar Model/i });
    expect(switchBtn).toBeInTheDocument();
    expect(switchBtn).toHaveTextContent("Hinaa (Original)");

    fireEvent.click(switchBtn);
    expect(screen.getByText("Select Companion Model")).toBeInTheDocument();

    const schoolgirlOption = screen.getByText("Sakura Student (Sample E)");
    fireEvent.click(schoolgirlOption);
    expect(onSelectModel).toHaveBeenCalledWith("/models/AvatarSample_E.vrm");
  });

  it("allows switching companion dock position between Left, Floating, and Right", () => {
    renderWorkMode({
      avatarModel: "/models/hinaa.vrm",
    });

    const companionPanel = screen.getByTestId("work-companion-panel");
    expect(companionPanel).toBeInTheDocument();

    const dockLeftBtn = screen.getByRole("button", { name: "Dock Left" });
    const floatBtn = screen.getByRole("button", { name: "Float Companion" });
    const dockRightBtn = screen.getByRole("button", { name: "Dock Right" });

    expect(dockLeftBtn).toBeInTheDocument();
    expect(floatBtn).toBeInTheDocument();
    expect(dockRightBtn).toBeInTheDocument();

    // Switch to Left Dock
    fireEvent.click(dockLeftBtn);
    expect(companionPanel.style.left).toBe("0px");

    // Switch to Floating
    fireEvent.click(floatBtn);
    expect(companionPanel.style.position).toBe("absolute");
    expect(companionPanel.style.width).toBe("320px");

    // Switch back to Right Dock
    fireEvent.click(dockRightBtn);
    expect(companionPanel.style.right).toBe("0px");
  });

  it("can hide and reopen the companion panel from the pill and header buttons", () => {
    renderWorkMode({
      avatarModel: "/models/hinaa.vrm",
    });

    expect(screen.getByTestId("work-companion-panel")).toBeInTheDocument();

    // Close via pill close button
    const hideBtn = screen.getByRole("button", { name: "Hide Companion" });
    fireEvent.click(hideBtn);

    expect(screen.queryByTestId("work-companion-panel")).not.toBeInTheDocument();

    // Reopen via header button
    const showHeaderBtn = screen.getByRole("button", { name: "Show companion panel" });
    fireEvent.click(showHeaderBtn);

    expect(screen.getByTestId("work-companion-panel")).toBeInTheDocument();
  });

  it("renders mobile mode switcher and allows switching to dedicated 3D avatar screen", () => {
    // Mock window.innerWidth to mobile
    const originalWidth = window.innerWidth;
    window.innerWidth = 390;
    window.dispatchEvent(new Event("resize"));

    try {
      renderWorkMode({
        avatarModel: "/models/hinaa.vrm",
      });

      // Mobile switcher should be visible
      const mobileSwitcher = screen.getByTestId("mobile-mode-switcher");
      expect(mobileSwitcher).toBeInTheDocument();

      // On mobile chat tab, companion panel is NOT rendered side-by-side
      expect(screen.queryByTestId("work-companion-panel")).not.toBeInTheDocument();
      // But floating jump pill IS rendered
      expect(screen.getByTestId("mobile-floating-avatar-pill")).toBeInTheDocument();

      // Click "🌸 3D Avatar" tab in header
      const avatarTabBtn = screen.getByTestId("mobile-tab-avatar");
      fireEvent.click(avatarTabBtn);

      // Now the dedicated mobile 3D avatar screen is active!
      expect(screen.getByTestId("mobile-avatar-screen")).toBeInTheDocument();
      expect(screen.getByTestId("mobile-back-to-chat")).toBeInTheDocument();

      // Click "Open Chat" to return to chat
      fireEvent.click(screen.getByTestId("mobile-back-to-chat"));
      expect(screen.queryByTestId("mobile-avatar-screen")).not.toBeInTheDocument();
    } finally {
      window.innerWidth = originalWidth;
      window.dispatchEvent(new Event("resize"));
    }
  });
});

describe("WorkMode command palette", () => {
  it("replaces the slash token with the chosen command instead of sending it", async () => {
    const onSend = vi.fn();

    // ComposerV6 renders a controlled textarea, so the palette has to be opened
    // by a real value transition; React skips onChange when the value is
    // unchanged, which is why seeding `input` directly never shows the popover.
    function Controlled() {
      const [value, setValue] = useState("");
      return <WorkMode {...defaultProps()} input={value} onInputChange={setValue} onSend={onSend} />;
    }

    render(<Controlled />);
    const composer = screen.getByRole("textbox", { name: "Message HINAA" });
    fireEvent.change(composer, { target: { value: "/sea" } });

    // Scoped to the popover: the "Web Search" label also appears elsewhere in
    // WorkMode, so a plain findByText can resolve before the command registry
    // has loaded and leave the palette with an empty list.
    await waitFor(() => {
      const popover = document.querySelector(".hinaa-command-popover");
      if (!popover?.textContent?.includes("Web Search")) throw new Error("palette list not populated");
    });

    fireEvent.keyDown(composer, { key: "Enter" });

    expect(screen.getByRole("textbox", { name: "Message HINAA" })).toHaveValue("/search ");
    expect(onSend).not.toHaveBeenCalled();
  });
});
