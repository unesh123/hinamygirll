import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PowerUpMentions } from "./PowerUpMentions";

describe("PowerUpMentions", () => {
  it("matches slash queries against /-aliases and surfaces the exact verb first", () => {
    render(<PowerUpMentions visible filter="research" sigil="/" onSelect={() => undefined} onClose={() => undefined} />);
    expect(screen.getByText("Deep Research")).toBeInTheDocument();
  });

  it("moves the selection with ArrowDown and submits the highlighted entry on Enter", () => {
    const onSelect = vi.fn();
    render(<PowerUpMentions visible filter="research" sigil="/" onSelect={onSelect} onClose={() => undefined} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "@research", slash: "/research" }));
  });

  it("closes instead of hijacking Enter when nothing matches", () => {
    const onClose = vi.fn();
    const onSelect = vi.fn();
    render(<PowerUpMentions visible filter="zzzz" sigil="/" onSelect={onSelect} onClose={onClose} />);
    expect(onClose).toHaveBeenCalled();
    expect(onSelect).not.toHaveBeenCalled();
  });
});
