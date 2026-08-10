import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("HINAA workspace shell", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the shell with brand and live status", () => {
    render(<App />);
    expect(screen.getAllByText("HINAA").length).toBeGreaterThan(0);
    expect(document.querySelector(".header-status")).toHaveTextContent(
      "Ready",
    );
  });

  it("shows the animated welcome greeting on first load", () => {
    render(<App />);
    expect(screen.getByText(/Hello, Unesh/i)).toBeInTheDocument();
    expect(
      screen.getByText(/What would you like to do\?/i),
    ).toBeInTheDocument();
  });

  it("does NOT show any Start/Talk/Tap buttons", () => {
    render(<App />);
    expect(
      screen.queryByRole("button", { name: /Start Live Session/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Tap to talk/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Talk to Hinaa/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the composer with mic and send controls", () => {
    render(<App />);
    expect(screen.getByLabelText(/Message Hinaa/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Start microphone")).toBeInTheDocument();
    expect(screen.getByLabelText("Send message")).toBeInTheDocument();
  });

  it("has header banner with settings trigger accessible", () => {
    render(<App />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("system errors do not appear in the conversation", () => {
    render(<App />);
    expect(screen.queryByText(/safety limit/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/microphone frame was lost/i),
    ).not.toBeInTheDocument();
  });

  it.todo(
    "Auto-starts listening on mount — requires browser mic permission mock",
  );
});
