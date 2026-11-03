import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HinaFloatingOverlay } from "./HinaFloatingOverlay";

vi.mock("framer-motion", () => ({ motion: { div: "div", aside: "aside" } }));

describe("floating companion animation lifecycle", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("does not schedule animation frames while the widget is closed", () => {
    const request = vi.fn(() => 1);
    vi.stubGlobal("requestAnimationFrame", request);
    render(<HinaFloatingOverlay isOpen={false} isWalking onClose={() => {}} />);
    expect(request).not.toHaveBeenCalled();
  });

  it("cancels its walk loop when the widget closes", () => {
    const request = vi.fn(() => 42);
    const cancel = vi.fn();
    vi.stubGlobal("requestAnimationFrame", request);
    vi.stubGlobal("cancelAnimationFrame", cancel);
    const { rerender } = render(<HinaFloatingOverlay isOpen isWalking onClose={() => {}} />);
    expect(request).toHaveBeenCalledOnce();
    rerender(<HinaFloatingOverlay isOpen={false} isWalking onClose={() => {}} />);
    expect(cancel).toHaveBeenCalledWith(42);
    expect(request).toHaveBeenCalledOnce();
  });
});
