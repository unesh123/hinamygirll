import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PremiumComposer } from "./PremiumComposer";

function ComposerHarness({ onPowerUp }: { onPowerUp: ReturnType<typeof vi.fn> }) {
  const [value, setValue] = useState("");
  return <PremiumComposer value={value} onChange={setValue} onSend={vi.fn()} onPowerUp={onPowerUp} />;
}

describe("PremiumComposer command surface", () => {
  it("opens the @ power-up palette and inserts a real intent tag", () => {
    const onPowerUp = vi.fn();
    render(<ComposerHarness onPowerUp={onPowerUp} />);

    const composer = screen.getByLabelText("Message HINAA");
    fireEvent.change(composer, { target: { value: "@" } });
    expect(screen.getByRole("button", { name: /Web Search/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Web Search/i }));
    expect(composer).toHaveValue("@search ");
    expect(onPowerUp).toHaveBeenCalledWith(expect.objectContaining({ action: "search-web" }));
  });

  it("opens the / command palette and resolves the selection to the same safe intent tag", () => {
    const onPowerUp = vi.fn();
    render(<ComposerHarness onPowerUp={onPowerUp} />);

    const composer = screen.getByLabelText("Message HINAA");
    fireEvent.change(composer, { target: { value: "/" } });
    expect(screen.getByText("/search")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Web Search/i }));
    expect(composer).toHaveValue("@search ");
    expect(onPowerUp).toHaveBeenCalledWith(expect.objectContaining({ action: "search-web" }));
  });
});
