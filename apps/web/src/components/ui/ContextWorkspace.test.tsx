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


describe("ContextWorkspace research progress", () => {
  it("shows actual research workflow stages instead of decorative third-party source graphics", () => {
    render(
      <ContextWorkspace
        mode="research"
        isSearching
        onClose={vi.fn()}
        steps={[
          { id: "scope", label: "Understand the question", detail: "Checking scope and evidence needs", status: "done" },
          { id: "sources", label: "Collect attributable sources", detail: "Using the configured research route", status: "active" },
          { id: "synthesis", label: "Prepare concise findings", detail: "Sources remain visible in chat", status: "pending" },
        ]}
      />,
    );

    expect(screen.getByLabelText("Research workflow")).toBeInTheDocument();
    expect(screen.getByText("Collect attributable sources")).toBeInTheDocument();
    expect(screen.getByText("Using the configured research route")).toBeInTheDocument();
    expect(screen.queryByText("Lightswind UI")).not.toBeInTheDocument();
    expect(screen.queryByText("YouTube")).not.toBeInTheDocument();
  });
});
