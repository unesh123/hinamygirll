import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { SidebarPanel } from "./SidebarPanel";

describe("SidebarPanel", () => {
  it("offers actual local tool actions instead of fabricated tool status data", () => {
    const openImageStudio = vi.fn();
    const openHumanizer = vi.fn();
    const openSettings = vi.fn();
    const prompt = vi.fn();
    render(
      <SidebarPanel
        section="tools"
        onClose={vi.fn()}
        onOpenImageStudio={openImageStudio}
        onOpenHumanizer={openHumanizer}
        onOpenSettings={openSettings}
        onQuickPrompt={prompt}
      />,
    );

    expect(screen.getByRole("heading", { name: "Choose an action, then stay in control" })).toBeInTheDocument();
    expect(screen.queryByText("Web Search")).not.toBeInTheDocument();
    expect(screen.queryByText("Ready")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Create an image/i }));
    expect(openImageStudio).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /Humanize a draft/i }));
    expect(openHumanizer).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /Research with sources/i }));
    expect(prompt).toHaveBeenCalledWith("Research this with clear sources and practical next steps: ");
  });

  it("starts a real new chat from the conversation section", () => {
    const newChat = vi.fn();
    render(<SidebarPanel section="chat" onClose={vi.fn()} onNewChat={newChat} />);
    expect(screen.queryByText("Previous chat")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /New conversation/i }));
    expect(newChat).toHaveBeenCalledTimes(1);
  });
});
