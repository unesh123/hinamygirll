import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ImageJobCard } from "./ImageJobCard";

afterEach(() => vi.unstubAllGlobals());

describe("image deliverables", () => {
  it("does not report completion without a generated image", () => {
    render(<ImageJobCard data={{ prompt: "A cup", stage: "saved" }} />);
    expect(screen.getByText("Generation Failed")).toBeInTheDocument();
    expect(screen.getByText("No generated image was returned. Please retry.")).toBeInTheDocument();
    expect(screen.queryByText("Completed")).not.toBeInTheDocument();
  });

  it.each([
    ["HTTP error", { ok: false, status: 401 }],
    ["HTML instead of an image", { ok: true, blob: async () => new Blob(["error"], { type: "text/html" }) }],
  ])("does not mark a failed download as saved: %s", async (_name, response) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    const commit = vi.fn();
    render(<ImageJobCard data={{ prompt: "A cup", stage: "saved", resultUrl: "/image.png" }} onCommit={commit} />);
    fireEvent.click(screen.getByRole("button", { name: "Download HD Image" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't download this image");
    expect(commit).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole("button", { name: "Download HD Image" })).toBeEnabled());
  });
});
