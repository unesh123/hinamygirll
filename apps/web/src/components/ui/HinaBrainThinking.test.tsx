import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HinaBrainThinking } from "./HinaBrainThinking";

describe("HinaBrainThinking", () => {
  it("renders nothing if there is no thought, no sources, and not live", () => {
    const { container } = render(<HinaBrainThinking />);
    expect(container.firstChild).toBeNull();
  });

  it("renders live thinking status during active streaming", () => {
    render(<HinaBrainThinking isLive={true} />);
    expect(screen.getByText("Hina is thinking & synthesizing...")).toBeInTheDocument();
  });

  it("renders live searching status when web search is active", () => {
    render(<HinaBrainThinking isLive={true} isSearching={true} searchQuery="latest AI news" />);
    expect(screen.getByText("Hina is searching web: latest AI news...")).toBeInTheDocument();
  });

  it("renders thought process and integrated sources in a collapsible brain container", () => {
    render(
      <HinaBrainThinking
        thought="Step 1: Analyzed user intent. Step 2: Formulated answer."
        sources={[
          {
            id: "S1",
            title: "Reuters Tech Update",
            url: "https://reuters.com/tech-news",
            snippet: "Breakthrough in AI models.",
          },
        ]}
        latencyMs={1400}
      />
    );

    // Initial state: shows badge with 1 source integrated and duration
    expect(screen.getByText("Thought Process & Brain Synthesis")).toBeInTheDocument();
    expect(screen.getByText("1 source integrated")).toBeInTheDocument();
    expect(screen.getByText("1.4s")).toBeInTheDocument();

    // Toggle expand
    fireEvent.click(screen.getByRole("button", { name: /Thought Process/i }));

    // Grounded knowledge base inside brain is displayed
    expect(screen.getByText("Grounded Knowledge Base (1)")).toBeInTheDocument();
    expect(screen.getByText("[1] reuters.com")).toBeInTheDocument();
    expect(screen.getByText("Step 1: Analyzed user intent. Step 2: Formulated answer.")).toBeInTheDocument();
  });
});
