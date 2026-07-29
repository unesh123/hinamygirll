import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("HINAA companion screen", () => {
  it("renders accessible mock and privacy status", () => {
    render(<App />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByText("Local mock")).toBeInTheDocument();
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
      () =>
        expect(
          screen.getByText(/Mock mode ekdam ready cha/),
        ).toBeInTheDocument(),
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
    const greeting = screen.getByText(/Ma Hinaa ko mock mode ho/);
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
});
