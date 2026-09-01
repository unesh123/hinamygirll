import { useState, useEffect } from "react";
import { fireEvent, render, screen, waitFor, findByText } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { PremiumComposer } from "./PremiumComposer";
import type { ContextItem, CommandItem } from "./PowerUpMentions";

// Mock the commands API response
const mockCommands: CommandItem[] = [
  {
    name: "search",
    aliases: ["search", "find", "lookup"],
    label: "Web Search",
    description: "Search the live web for current information with cited sources",
    descriptionShort: "Web search with citations",
    icon: "Search",
    color: "#0891b2",
    group: "Search & Research",
    inputSchema: { type: "object", properties: { query: { type: "string" } } },
    capability: "web_search",
    riskLevel: "read",
    approvalPolicy: "session-consent",
    availability: "available",
    executionLocation: "api",
    requiresAuth: false,
    examples: ["/search latest official Vite PWA documentation"],
  },
  {
    name: "research",
    aliases: ["research", "investigate", "deep research"],
    label: "Deep Research",
    description: "Multi-step cited research with configurable depth",
    descriptionShort: "Deep cited research",
    icon: "Brain",
    color: "#7c3aed",
    group: "Search & Research",
    inputSchema: { type: "object", properties: { query: { type: "string" } } },
    capability: "web_research",
    riskLevel: "low-mutation",
    approvalPolicy: "always-confirm",
    availability: "available",
    executionLocation: "api",
    requiresAuth: false,
    examples: ["/research current VRM lip-sync techniques"],
  },
];

const mockContexts: ContextItem[] = [
  {
    id: "project",
    kind: "project",
    label: "Current Project",
    description: "Reference the active project",
    icon: "GitBranch",
    color: "#7c3aed",
    sourceId: "current",
    access: "read",
  },
  {
    id: "conversation",
    kind: "conversation",
    label: "This Conversation",
    description: "Reference recent messages",
    icon: "MessageSquare",
    color: "#14b8a6",
    sourceId: "current",
    access: "read",
  },
];

function ComposerHarness({ onPowerUp }: { onPowerUp: ReturnType<typeof vi.fn> }) {
  const [value, setValue] = useState("");
  return (
    <PremiumComposer
      value={value}
      onChange={setValue}
      onSend={vi.fn()}
      onPowerUp={onPowerUp}
      commands={mockCommands}
      contexts={mockContexts}
    />
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: async () => ({ commands: mockCommands }),
  });
});

describe("PremiumComposer command surface", () => {
  it("opens the @ power-up palette and inserts a real intent tag", async () => {
    const onPowerUp = vi.fn();
    render(<ComposerHarness onPowerUp={onPowerUp} />);

    const composer = screen.getByLabelText("Message HINAA");
    fireEvent.change(composer, { target: { value: "@" } });
    
    // Wait for commands to load and context picker to appear
    await waitFor(() => {
      expect(screen.getByText(/@ Contexts \(2\)/)).toBeInTheDocument();
    });

    // Click on the first context (project)
    const projectButton = screen.getByText(/Current Project/);
    fireEvent.click(projectButton);
    expect(composer).toHaveValue("@project:current ");
    expect(onPowerUp).toHaveBeenCalledWith(expect.objectContaining({ kind: "project" }));
  });

  it("opens the / command palette and resolves the selection to the same safe intent tag", async () => {
    const onPowerUp = vi.fn();
    render(<ComposerHarness onPowerUp={onPowerUp} />);

    const composer = screen.getByLabelText("Message HINAA");
    fireEvent.change(composer, { target: { value: "/" } });
    
    // Wait for commands to load and command palette to appear
    await waitFor(() => {
      expect(screen.getByText(/\/ Commands \(2\)/)).toBeInTheDocument();
    });

    // Wait for animations to complete
    await waitFor(() => {}, { timeout: 2000 });

    // Find and click the search command button (exact label matches the leaf
    // div only, avoiding ancestor elements whose textContent also contains it)
    const searchButton = await screen.findByText("Web Search", {}, { timeout: 15000 });
    expect(searchButton).toBeInTheDocument();
    fireEvent.click(searchButton);

    expect(composer).toHaveValue("/search ");
    expect(onPowerUp).toHaveBeenCalledWith(expect.objectContaining({ name: "search" }));
  });
});