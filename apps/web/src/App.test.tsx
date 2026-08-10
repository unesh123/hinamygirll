import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("HINAA Gemini-mobile stage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the main stage with brand and status", () => {
    render(<App />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByText("HINAA")).toBeInTheDocument();
    // Header status pill shows the live state…
    expect(document.querySelector(".header-status")).toHaveTextContent(
      "Ready",
    );
    // …and the companion profile card carries identity + same state.
    const card = document.querySelector(".companion-profile-card");
    expect(card).not.toBeNull();
    expect(card).toHaveTextContent("Hinaa");
    expect(card).toHaveTextContent("Ready");
  });

  it("does NOT show any Start/Talk/Tap buttons", () => {
    render(<App />);
    expect(screen.queryByRole("button", { name: /Start Live Session/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tap to talk/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Talk to Hinaa/i })).not.toBeInTheDocument();
  });

  it("shows the text composer fallback when live voice is not active", () => {
    render(<App />);
    expect(screen.getByLabelText("Type a message")).toBeInTheDocument();
  });

  it("shows tap hint when idle", () => {
    render(<App />);
    expect(screen.getByText(/Tap anywhere to start talking/i)).toBeInTheDocument();
  });

  it("has settings trigger accessible", () => {
    render(<App />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("system errors do not appear in the conversation", () => {
    render(<App />);
    expect(screen.queryByText(/safety limit/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/microphone frame was lost/i)).not.toBeInTheDocument();
  });

  it.todo(
    "Auto-starts listening on mount — requires browser mic permission mock"
  );

  it.todo(
    "Tap anywhere restarts session after error — requires mic permission mock"
  );
});
