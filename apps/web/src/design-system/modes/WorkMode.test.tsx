import { useState } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkMode } from "./WorkMode";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
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
  it("shows the image a user attached inside their own bubble", () => {
    const dataUrl = "data:image/png;base64,aGVsbG8=";
    renderWorkMode({ messages: [
      { id: "user", role: "user", text: "Use this as the face reference", createdAt: new Date().toISOString(), imageUrl: dataUrl },
      { id: "answer", role: "assistant", text: "Got it, I can see the face.", createdAt: new Date().toISOString() },
    ] });

    const attached = screen.getByRole("img", { name: "Your attached image" });
    expect(attached).toHaveAttribute("src", dataUrl);
  });

  it("sends the chosen role with the message that carries the picture", () => {
    const dataUrl = "data:image/png;base64,aGVsbG8=";
    const onSend = vi.fn();
    // The picker keeps its own state inside ComposerV6, so the send has to be
    // triggered by a real click on the send button, not by calling onSend.
    function Controlled() {
      const [value, setValue] = useState("");
      return (
        <WorkMode
          {...defaultProps()}
          input={value}
          onInputChange={setValue}
          onSend={onSend}
          attachedImage={dataUrl}
        />
      );
    }

    render(<Controlled />);
    fireEvent.change(screen.getByRole("textbox", { name: "Message HINAA" }), {
      target: { value: "make it like this" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Role: Style" }));
    fireEvent.click(screen.getByText("Face Identity"));
    fireEvent.click(screen.getByTestId("composer-send-btn"));

    expect(onSend).toHaveBeenCalledWith("make it like this", "face_reference");
  });

  it("labels the attached picture with the role it was sent as", () => {
    const dataUrl = "data:image/png;base64,aGVsbG8=";
    renderWorkMode({
      messages: [
        {
          id: "user",
          role: "user",
          text: "make it like this",
          createdAt: new Date().toISOString(),
          imageUrl: dataUrl,
          attachments: [{ kind: "image", role: "face_reference", url: dataUrl }],
        },
        { id: "answer", role: "assistant", text: "On it — face locked.", createdAt: new Date().toISOString() },
      ],
    });

    expect(screen.getByRole("img", { name: "Your attached image" })).toBeInTheDocument();
    expect(screen.getByText("Face Identity")).toBeInTheDocument();
  });

  it("does not invent a role label for an unlabelled picture", () => {
    const dataUrl = "data:image/png;base64,aGVsbG8=";
    renderWorkMode({
      messages: [
        {
          id: "user",
          role: "user",
          text: "look at this",
          createdAt: new Date().toISOString(),
          imageUrl: dataUrl,
          attachments: [{ kind: "image", url: dataUrl }],
        },
        { id: "answer", role: "assistant", text: "I see a terminal.", createdAt: new Date().toISOString() },
      ],
    });

    expect(screen.getByRole("img", { name: "Your attached image" })).toBeInTheDocument();
    expect(screen.queryByText("Face Identity")).not.toBeInTheDocument();
    expect(screen.queryByText("Style Reference")).not.toBeInTheDocument();
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

  it("reports an unmeasured brain as untested instead of ready", () => {
    renderWorkMode({
      activeProviderMode: "claude",
      activeProviderModel: "claude-sonnet-4-6",
      providerHealth: "untested",
    });

    const statusLine = screen.getByTestId("provider-micro-status");
    expect(statusLine).toHaveTextContent("Not tested yet");
    expect(statusLine).not.toHaveTextContent("Ready");
  });

  it("switches to the brain the backend measured as answering", () => {
    const onSelectProvider = vi.fn();
    renderWorkMode({
      activeProviderMode: "cx-gateway",
      providerHealth: "unavailable",
      brainRecovery: { mode: "real", model: "gemini-2.5-flash" },
      onSelectProvider,
    });

    const fallbackBtn = screen.getByTestId("micro-status-recovery");
    expect(fallbackBtn).toHaveTextContent("Switch to Gemini");
    fireEvent.click(fallbackBtn);
    expect(onSelectProvider).toHaveBeenCalledWith("real", "gemini-2.5-flash");
  });

  it("offers no switch when no brain has answered a live call", () => {
    renderWorkMode({
      activeProviderMode: "cx-gateway",
      providerHealth: "unavailable",
      brainRecovery: null,
      onSelectProvider: vi.fn(),
    });

    // The row used to name Gemini whatever the backend had actually proved.
    expect(screen.queryByTestId("micro-status-recovery")).not.toBeInTheDocument();
    expect(screen.getByTestId("provider-micro-status")).toHaveTextContent("Offline");
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
      brainRecovery: { mode: "real", model: "gemini-2.5-flash" },
      onSelectProvider,
      onRetry,
    });

    const recoveryCard = screen.getByTestId("rate-limit-recovery-card");
    expect(recoveryCard).toBeInTheDocument();
    expect(screen.getByText(/Brain Model Rate Limit \/ Cooldown Active/i)).toBeInTheDocument();

    const switchBtn = screen.getByTestId("brain-recovery-switch");
    expect(switchBtn).toHaveTextContent("Switch to Gemini");
    fireEvent.click(switchBtn);
    expect(onSelectProvider).toHaveBeenCalledWith("real", "gemini-2.5-flash");

    const retryBtn = screen.getByRole("button", { name: /Retry Prompt/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not name a brain the backend has not proven during a rate limit", () => {
    const userMsg: TranscriptMessage = {
      id: "u-1",
      role: "user",
      text: "Write a high-frequency trading bot in Python",
      createdAt: new Date().toISOString(),
    };
    const rateLimitedMessage: TranscriptMessage = {
      id: "err-1",
      role: "assistant",
      text: "Rate limit exceeded on the selected model.",
      createdAt: new Date().toISOString(),
    };

    renderWorkMode({
      messages: [userMsg, rateLimitedMessage],
      brainRecovery: null,
      onSelectProvider: vi.fn(),
    });

    expect(screen.getByTestId("rate-limit-recovery-card")).toHaveTextContent(
      "no other brain has answered a live call yet",
    );
    expect(screen.queryByTestId("brain-recovery-switch")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry Prompt/i })).toBeInTheDocument();
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
      // No floating pill — the header switcher is the only entry point, so the
      // message list and the "Latest" button stay unobstructed.
      expect(screen.queryByTestId("mobile-floating-avatar-pill")).not.toBeInTheDocument();

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

describe("WorkMode execution progress placement", () => {
  it("renders the running card inside the transcript instead of over the composer", () => {
    renderWorkMode({
      isThinking: true,
      agentSteps: [
        { id: "accepted", label: "Run accepted", status: "done" },
        { id: "plan", label: "Plan ready", status: "done" },
        { id: "answer", label: "Generate assistant response", status: "active" },
      ],
    });

    const card = screen.getByTestId("agent-activity-card");
    const transcript = document.querySelector(".hinaa-work-transcript");

    // The transcript scrolls, the composer does not — a card in the latter
    // floats over the middle of the chat on a phone.
    expect(transcript?.contains(card)).toBe(true);
    expect(screen.getByTestId("work-composer").contains(card)).toBe(false);
  });
});

function assistantWithActivity(status: string, withPlan = false) {
  return [
    { id: "u1", role: "user" as const, text: "make me a pdf", createdAt: new Date().toISOString() },
    {
      id: "a1",
      role: "assistant" as const,
      text: "Your PDF is ready to build.",
      createdAt: new Date().toISOString(),
      ...(withPlan
        ? { plan: { toolRequests: [{ toolName: "pdf_generate", parameters: {} }] } as unknown as AssistantTurnPlan }
        : {}),
      toolActivity: [{ id: "pdf_generate", status, label: `Working locally: pdf_generate` }],
    },
  ];
}

describe("WorkMode progress while a tool runs", () => {
  it("keeps a running action visible after the turn stream closes", () => {
    renderWorkMode({ isThinking: false, messages: assistantWithActivity("running") });

    expect(screen.getByTestId("agent-activity-card")).toBeInTheDocument();
    expect(screen.getByTestId("activity-step-pdf_generate")).toHaveTextContent(
      "Working locally: pdf_generate",
    );
  });

  it("publishes the running action as a polite live region", () => {
    renderWorkMode({ isThinking: false, messages: assistantWithActivity("running") });

    const live = screen.getByTestId("agent-activity-card").querySelector("[data-tool-activity]");
    expect(live).toHaveAttribute("role", "status");
    expect(live).toHaveAttribute("aria-live", "polite");
  });

  it("clears the card once the action settles", () => {
    renderWorkMode({ isThinking: false, messages: assistantWithActivity("complete") });

    expect(screen.queryByTestId("agent-activity-card")).not.toBeInTheDocument();
  });

  it("does not call an unapproved proposal active execution", () => {
    renderWorkMode({ isThinking: false, messages: assistantWithActivity("pending", true) });

    expect(screen.queryByTestId("agent-activity-card")).not.toBeInTheDocument();
    expect(screen.getByTestId("tool-approval")).toBeInTheDocument();
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
      const selected = document.querySelector(
        ".hinaa-command-popover [data-selected='true']",
      );
      if (!selected?.textContent?.includes("Web Search")) {
        throw new Error("palette has no highlighted command yet");
      }
    });

    await act(async () => {
      fireEvent.keyDown(composer, { key: "Enter" });
    });

    expect(screen.getByRole("textbox", { name: "Message HINAA" })).toHaveValue("/search ");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("opens a browser-served command surface instead of leaving its token behind", async () => {
    const onCommand = vi.fn();
    const onSend = vi.fn();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/v1/commands")) {
        return {
          ok: true,
          json: async () => ({
            commands: [
              {
                name: "settings",
                label: "Settings",
                description: "Open or modify settings",
                descriptionShort: "Open settings",
                capability: "settings",
                executionLocation: "browser",
                availability: "available",
              },
            ],
          }),
        };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    });
    vi.stubGlobal("fetch", fetchMock);

    function Controlled() {
      const [value, setValue] = useState("");
      return (
        <WorkMode
          {...defaultProps()}
          input={value}
          onInputChange={setValue}
          onSend={onSend}
          onCommand={onCommand}
        />
      );
    }

    try {
      render(<Controlled />);
      const composer = screen.getByRole("textbox", { name: "Message HINAA" });
      fireEvent.change(composer, { target: { value: "/set" } });

      await waitFor(() => {
        const selected = document.querySelector(".hinaa-command-popover [data-selected='true']");
        if (!selected?.textContent?.includes("Settings")) {
          throw new Error("the settings command is not highlighted yet");
        }
      });

      await act(async () => {
        fireEvent.keyDown(composer, { key: "Enter" });
      });

      expect(onCommand).toHaveBeenCalledWith("open-settings");
      expect(composer).toHaveValue("");
      expect(onSend).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("prefers the command named by the typed word over one that only mentions it", async () => {
    const onCommand = vi.fn();
    // Mirrors the live registry order, where voice is listed first and its
    // description contains the word "settings".
    const rows = [
      {
        name: "voice",
        label: "Voice",
        description: "Configure voice settings or test TTS",
        descriptionShort: "Voice settings",
        capability: "voice-config",
        executionLocation: "api",
        availability: "available",
      },
      {
        name: "settings",
        label: "Settings",
        description: "Open or modify settings",
        descriptionShort: "Open settings",
        capability: "settings",
        executionLocation: "browser",
        availability: "available",
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/v1/commands")) {
          return { ok: true, json: async () => ({ commands: rows }) };
        }
        return { ok: false, status: 404, json: async () => ({}) };
      }),
    );

    function Controlled() {
      const [value, setValue] = useState("");
      return (
        <WorkMode
          {...defaultProps()}
          input={value}
          onInputChange={setValue}
          onCommand={onCommand}
        />
      );
    }

    try {
      render(<Controlled />);
      const composer = screen.getByRole("textbox", { name: "Message HINAA" });
      fireEvent.change(composer, { target: { value: "/settings" } });

      await waitFor(() => {
        const selected = document.querySelector(".hinaa-command-popover [data-selected='true']");
        if (!selected?.textContent?.includes("Settings")) {
          throw new Error(`wrong row is highlighted: ${selected?.textContent ?? "none"}`);
        }
      });

      await act(async () => {
        fireEvent.keyDown(composer, { key: "Enter" });
      });

      expect(onCommand).toHaveBeenCalledWith("open-settings");
      expect(composer).toHaveValue("");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  describe("In-thread Action Objects", () => {
    it("renders committed reminder object in the thread message list with NOT WIRED status", () => {
      const messages = [
        { id: "u1", role: "user" as const, text: "remind me tomorrow at 8 to call Alex", createdAt: new Date().toISOString() },
        {
          id: "a1",
          role: "assistant" as const,
          text: "Reminder scheduled: call Alex · Tomorrow · 8:00 AM",
          createdAt: new Date().toISOString(),
          actionDraft: {
            id: "draft-remind-1",
            intent: "reminder.create",
            fields: {
              data: {
                title: "call Alex",
                when: "Tomorrow · 8:00 AM",
                isUrgent: false,
              },
            },
            status: "success",
          },
        },
      ];

      renderWorkMode({ messages });

      // Verifies title and when remain visible in the thread
      expect(screen.getByText("call Alex")).toBeInTheDocument();
      expect(screen.getByText("Tomorrow · 8:00 AM")).toBeInTheDocument();
      // Verifies honest button marking
      expect(screen.getByText("NOT WIRED")).toBeInTheDocument();
      expect(screen.getByText("Reminder active in thread")).toBeInTheDocument();
    });

    it("renders image generation object in the thread message list with live timer", () => {
      const messages = [
        { id: "u1", role: "user" as const, text: "generate a red mug", createdAt: new Date().toISOString() },
        {
          id: "a1",
          role: "assistant" as const,
          text: 'Generating image for "Red mug"',
          createdAt: new Date().toISOString(),
          actionDraft: {
            id: "draft-img-1",
            intent: "image.job",
            fields: {
              data: {
                prompt: "Red mug",
                aspectRatio: "16:9",
                style: "photorealistic",
                stage: "generating",
                elapsedSeconds: 0,
              },
            },
            status: "running",
          },
        },
      ];

      renderWorkMode({ messages });

      // Verifies Image Generation Object in the message list
      expect(screen.getByText("Image Generation Object")).toBeInTheDocument();
      expect(screen.getByText(/Generating · \d+s/)).toBeInTheDocument();
      expect(screen.getByText("Red mug")).toBeInTheDocument();
    });
  });
});
