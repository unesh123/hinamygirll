import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThinkingWeave } from "./ThinkingWeave";

describe("ThinkingWeave", () => {
  it("streams the latest live reasoning line with a duration readout", () => {
    render(
      <ThinkingWeave
        thoughts={["Reading the request.", "Two candidate routes found; checking auth."]
          .map((t) => t)
        }
        durationMs={3400}
      />,
    );
    expect(screen.getByText("Two candidate routes found; checking auth.")).toBeInTheDocument();
    expect(screen.getByText("3.4s")).toBeInTheDocument();
  });

  it("reveals the full thought chain on demand", () => {
    render(
      <ThinkingWeave
        thoughts={["First thought.", "Second thought.", "Third thought."]}
        durationMs={1200}
      />,
    );
    const toggle = screen.getByRole("button", { name: /watch the weave \(3\)/ });
    expect(screen.queryByText("First thought.")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByText("First thought.")).toBeInTheDocument();
    // "Third thought." now appears twice: live line + chain entry — proof the
    // ordered list rendered in full.
    expect(screen.getAllByText("Third thought.")).toHaveLength(2);
  });

  it("stays silent without thoughts — legacy spinner behaviour", () => {
    render(<ThinkingWeave />);
    expect(screen.queryByText(/watch the weave/)).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
