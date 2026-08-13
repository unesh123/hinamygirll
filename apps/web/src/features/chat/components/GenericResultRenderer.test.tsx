import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GenericResultRenderer } from "./GenericResultRenderer";

describe("GenericResultRenderer", () => {
  it("discloses the actual public search fallback while preserving attributed sources", () => {
    render(
      <GenericResultRenderer
        toolName="web_search"
        result={{
          provider: "public-fallback",
          notice: "You.com is not configured in this local runtime; HINAA used the public fallback search.",
          sources: [
            {
              id: "S1",
              title: "Example source",
              url: "https://example.com/research",
              snippet: "A verifiable research snippet.",
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("HINAA used the public fallback search");
    expect(screen.getByText("Example source")).toBeInTheDocument();
    expect(screen.getByText("1 attributed result")).toBeInTheDocument();
  });

  it("renders a provider recovery state instead of an empty source list on web-search failure", () => {
    render(
      <GenericResultRenderer
        toolName="web_search"
        result={{
          status: "error",
          code: "YOUCOM_TIMEOUT",
          error: "You.com did not respond before HINAA's local timeout.",
          sources: [],
        }}
      />,
    );

    expect(screen.getByLabelText("Research service recovery")).toHaveTextContent("Research service needs attention");
    expect(screen.getByText(/Try a narrower query or retry shortly/i)).toBeInTheDocument();
    expect(screen.queryByText("No attributable sources were returned for this query.")).not.toBeInTheDocument();
  });
});
