import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocalHumanizerStudio } from "./LocalHumanizerStudio";

describe("LocalHumanizerStudio", () => {
  afterEach(() => vi.restoreAllMocks());

  it("uses the private local route and renders the polished result", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        text: "Also, we use this example.",
        style: "natural",
        route: "local-deterministic",
        externalTextTransfer: false,
        changes: ["Simplified wording"],
        originalCharacterCount: 42,
        outputCharacterCount: 30,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<LocalHumanizerStudio onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Text to humanize"), { target: { value: "Additionally, we utilize this example." } });
    fireEvent.click(screen.getByRole("button", { name: "Humanize text" }));

    await waitFor(() => expect(screen.getByLabelText("Humanized result")).toHaveValue("Also, we use this example."));
    expect(screen.getByText(/Finished locally/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/text/humanize", expect.objectContaining({ method: "POST" }));
  });
});
