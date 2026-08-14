import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocalHumanizerStudio } from "./LocalHumanizerStudio";

const polishedResult = {
  text: "Also, we use C:\\HINAA\\brief.md [1].",
  style: "concise",
  route: "local-deterministic",
  externalTextTransfer: false,
  changes: ["Simplified wording", "Protected technical spans and citations"],
  originalCharacterCount: 56,
  outputCharacterCount: 41,
  protectedSegmentCount: 2,
  protectedCharacterCount: 22,
};

describe("LocalHumanizerStudio", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("uses the private local route and renders the polished result", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...polishedResult, text: "Also, we use this example.", style: "natural" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<LocalHumanizerStudio onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Text to humanize"), { target: { value: "Additionally, we utilize this example." } });
    fireEvent.click(screen.getByRole("button", { name: "Humanize text" }));

    await waitFor(() => expect(screen.getByLabelText("Humanized result")).toHaveValue("Also, we use this example."));
    expect(screen.getByText(/Finished locally/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/text/humanize", expect.objectContaining({ method: "POST" }));
  });

  it("shows protected-span feedback and restores the original local draft", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => polishedResult });
    vi.stubGlobal("fetch", fetchMock);
    render(<LocalHumanizerStudio onClose={vi.fn()} />);

    const draft = screen.getByLabelText("Text to humanize");
    fireEvent.change(draft, { target: { value: "Additionally, we utilize C:\\HINAA\\brief.md [1]." } });
    fireEvent.click(screen.getByRole("button", { name: "Humanize text" }));

    await waitFor(() => expect(screen.getByText(/2 protected spans/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Use as draft" }));
    expect(draft).toHaveValue("Also, we use C:\\HINAA\\brief.md [1].");
    fireEvent.click(screen.getByRole("button", { name: "Restore original" }));
    expect(draft).toHaveValue("Additionally, we utilize C:\\HINAA\\brief.md [1].");
  });

  it("saves a completed local draft only to the selected private project", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => polishedResult })
      .mockResolvedValueOnce({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.setItem("hinaa-active-project-id", "project-7");
    render(<LocalHumanizerStudio onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Text to humanize"), { target: { value: "Additionally, we utilize C:\\HINAA\\brief.md [1]." } });
    fireEvent.click(screen.getByRole("button", { name: "Humanize text" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Save to project" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Save to project" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Saved to project" })).toBeDisabled());
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/projects/project-7/artifacts");
    const request = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(request.method).toBe("POST");
    expect(JSON.parse(String(request.body))).toMatchObject({
      kind: "document",
      title: "Humanized concise draft",
      content: polishedResult.text,
      metadata: { origin: "local-humanizer", externalTextTransfer: false, protectedSegmentCount: 2 },
    });
  });
});
