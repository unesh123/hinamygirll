import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ContextWorkspace } from "./ContextWorkspace";

describe("ContextWorkspace", () => {
  it("explains research and browser empty states without reusing an image placeholder", () => {
    const { rerender } = render(<ContextWorkspace mode="research" onClose={vi.fn()} />);
    expect(screen.getByText(/Attributed sources will appear here/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close Research workspace" })).toBeInTheDocument();
    expect(screen.queryByText("Images appear inline in the chat")).not.toBeInTheDocument();

    rerender(<ContextWorkspace mode="browser" onClose={vi.fn()} />);
    expect(screen.getByText(/Browser actions are proposed clearly before they run/i)).toBeInTheDocument();
  });
});
