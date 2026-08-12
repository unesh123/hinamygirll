import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("HINAA assistant workspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.removeItem("hinaa.avatar-model");
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

  it.todo("starts live voice only after the user grants microphone permission");
  it.todo("offers a visible confirmation before executing an external assistant action");
});
