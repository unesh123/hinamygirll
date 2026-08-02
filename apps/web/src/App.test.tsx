import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("HINAA companion screen", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders accessible mock and privacy status", () => {
    render(<App />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByLabelText("Voice status")).toHaveTextContent(
      "Voice ready",
    );
    expect(screen.getByText(/No API key/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /simulate microphone listening/i }),
    ).toBeInTheDocument();
  });

  it("sends text through the deterministic mock provider", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Type a message"), "Namaste");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(screen.getByText("Namaste", { selector: "p" })).toBeInTheDocument();
    await waitFor(
      () => expect(screen.getByText(/Mock mode UI test/i)).toBeInTheDocument(),
      { timeout: 4000 },
    );
  });

  it("switches to text-only and reduced-motion modes", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Text only/ }));
    expect(screen.getByTestId("text-only-avatar")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /Reduced motion off/ }),
    );
    expect(
      screen.getByRole("button", { name: /Reduced motion on/ }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("simulates listening and allows safe interruption", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      screen.getByRole("button", { name: /simulate microphone listening/i }),
    );
    expect(screen.getByText("Listening")).toBeInTheDocument();
    expect(screen.getByTestId("partial-transcript")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Stop current turn/ }));
    expect(screen.getByText("Interrupted")).toBeInTheDocument();
  });

  it("switches companion profiles without losing the transcript", async () => {
    const user = userEvent.setup();
    render(<App />);
    const greeting = screen.getByText(/Hinaa ready cha/);
    await user.click(
      screen.getByRole("button", { name: /HiroCalm & helpful/ }),
    );
    expect(
      screen.getByText("Hiro", { selector: ".chat-header strong" }),
    ).toBeInTheDocument();
    expect(greeting).toBeInTheDocument();
  });

  it("recovers to a user-readable error state for a deterministic mock failure", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Type a message"), "/error");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(screen.getByText("Error")).toBeInTheDocument(), {
      timeout: 2000,
    });
    expect(screen.getByText(/failed safely/i)).toBeInTheDocument();
  });

  it("auto-selects Microsoft voice with OpenAI brain when both providers are ready", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: "openai",
              capabilities: [
                "llm",
                "structured-turn-plan",
                "text-stream",
                "model:gpt-5-mini",
                "model:gpt-5.6-luna",
              ],
              state: "healthy",
              userMessage: "OpenAI ready.",
            },
            {
              id: "azure-speech",
              capabilities: ["stt", "tts", "ne-NP"],
              state: "healthy",
              userMessage: "Microsoft Speech ready.",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<App />);

    await waitFor(() =>
      expect(screen.getByLabelText("Voice status")).toHaveTextContent(
        "Microsoft voice",
      ),
    );
    await user.click(screen.getByText("Advanced voice settings"));
    expect(screen.getByLabelText("Provider mode")).toHaveValue("openai");
    expect(screen.getByLabelText("Brain model")).toHaveValue("gpt-5-mini");
    await user.selectOptions(
      screen.getByLabelText("Brain model"),
      "gpt-5.6-luna",
    );
    expect(screen.getByLabelText("Brain model")).toHaveValue("gpt-5.6-luna");
  });

  it("blocks local microphone controls until local STT is configured", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: "local",
              capabilities: [
                "llm",
                "zero-credit",
                "offline",
                "stt-unconfigured",
              ],
              state: "degraded",
              userMessage: "Local STT is not configured.",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<App />);
    await user.click(screen.getByText("Advanced voice settings"));
    expect(
      screen.getByRole("option", { name: /Groq fast brain/i }),
    ).toHaveValue("groq");
    expect(
      screen.getByRole("option", { name: /Microsoft voice \+ OpenAI brain/i }),
    ).toHaveValue("openai");
    await user.selectOptions(screen.getByLabelText("Provider mode"), "local");

    expect(
      await screen.findByText(/hands-free local mic is disabled/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Talk to Hinaa/ }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Start microphone recording/ }),
    ).toBeDisabled();
  });
});
