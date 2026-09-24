import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PushToTalkButton } from "./PushToTalkButton";

describe("hold to speak", () => {
  it("releases exactly once on keyboard focus loss", () => {
    const start = vi.fn(); const stop = vi.fn();
    render(<PushToTalkButton onStart={start} onStop={stop} />);
    const button = screen.getByRole("button", { name: "Hold to speak" });
    fireEvent.keyDown(button, { key: " " });
    fireEvent.keyDown(button, { key: " ", repeat: true });
    fireEvent.blur(button);
    fireEvent.keyUp(button, { key: " " });
    expect(start).toHaveBeenCalledTimes(1);
    expect(stop).toHaveBeenCalledTimes(1);
  });
  it("releases an active capture when unmounted", () => {
    const stop = vi.fn();
    const view = render(<PushToTalkButton onStart={vi.fn()} onStop={stop} />);
    fireEvent.keyDown(screen.getByRole("button", { name: "Hold to speak" }), { key: "Enter" });
    view.unmount();
    expect(stop).toHaveBeenCalledTimes(1);
  });
});
