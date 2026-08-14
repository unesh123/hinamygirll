import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ContextWorkspace } from "./ContextWorkspace";

const source = {
  id: "source-1",
  title: "Local-first research guide",
  domain: "example.test",
  snippet: "A concise attributable source preview.",
  url: "https://example.test/research",
};

describe("ContextWorkspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("explains research and browser empty states without reusing an image placeholder", () => {
    const { rerender } = render(<ContextWorkspace mode="research" onClose={vi.fn()} />);
    expect(screen.getByText(/Attributed sources will appear here/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close Research workspace" })).toBeInTheDocument();
    expect(screen.queryByText("Images appear inline in the chat")).not.toBeInTheDocument();

    rerender(<ContextWorkspace mode="browser" onClose={vi.fn()} />);
    expect(screen.getByText(/Browser actions are proposed clearly before they run/i)).toBeInTheDocument();
  });

  it("renders attributable sources and saves a user-selected source only to the active local project", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.setItem("hinaa-active-project-id", "research-project");
    render(<ContextWorkspace mode="research" onClose={vi.fn()} sources={[source]} />);

    expect(screen.getByLabelText("Attributable research sources")).toBeInTheDocument();
    expect(screen.getByText("1 attributable source")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText("Saved to the active local project.")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/projects/research-project/artifacts", expect.objectContaining({ method: "POST" }));
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      kind: "research",
      title: source.title,
      sourceUrl: source.url,
      metadata: { origin: "research-source-card", domain: source.domain },
    });
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
