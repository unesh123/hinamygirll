import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ComposerV6 } from "./ComposerV6";

function renderComposer() {
  const onSelectArtifact = vi.fn();
  render(
    <ComposerV6 value="" onChange={vi.fn()} onSend={vi.fn()} onSelectArtifact={onSelectArtifact} />,
  );
  fireEvent.click(screen.getByTestId("composer-plus-btn"));
  return onSelectArtifact;
}

describe("ComposerV6 plus menu", () => {
  it("offers only the attachment the turn payload can actually carry", () => {
    renderComposer();

    expect(screen.getByRole("button", { name: /Upload Image/ })).toBeInTheDocument();
    // These called an onUploadFile prop no parent ever passed, so they did nothing.
    for (const label of ["Upload Audio", "Upload Document", "Upload Video", "Take Photo"]) {
      expect(screen.queryByRole("button", { name: label })).not.toBeInTheDocument();
    }
  });

  it("does not offer context chips or integrations that never reach the backend", () => {
    renderComposer();

    for (const label of [
      "Active Project",
      "GitHub Repo",
      "Live Canvas",
      "Paste URL",
      "Google Drive",
      "Notion",
      "Slack",
    ]) {
      expect(screen.queryByRole("button", { name: label })).not.toBeInTheDocument();
    }
  });

  it("hands the parent a real slash command for every create action", () => {
    const onSelectArtifact = renderComposer();

    // Website, Spreadsheet, Video, Code and Diagram had no command behind them.
    for (const label of ["Website", "Spreadsheet", "Video", "Code", "Diagram"]) {
      expect(screen.queryByRole("button", { name: label })).not.toBeInTheDocument();
    }

    fireEvent.click(screen.getByRole("button", { name: "Presentation" }));
    expect(onSelectArtifact).toHaveBeenCalledWith("/presentation");
  });
});
