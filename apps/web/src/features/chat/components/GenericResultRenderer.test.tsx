import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GenericResultRenderer } from "./GenericResultRenderer";

describe("GenericResultRenderer", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("persists exact gallery-card selection with result-set identity", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "selected" }), { status: 200 }),
    );
    render(
      <GenericResultRenderer
        toolName="image_search"
        conversationId="conv-mikasa"
        result={{
          canonicalSubject: "Mikasa Ackerman",
          resultSet: { resultSetId: "RS_MIKASA" },
          images: [
            { id: "IMG_A", imageUrl: "https://example.test/a.jpg", title: "Mikasa one", pageUrl: "https://example.test/a" },
            { id: "IMG_B", imageUrl: "https://example.test/b.jpg", title: "Mikasa two", pageUrl: "https://example.test/b" },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /select image 2/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/conversations/conv-mikasa/assets/select",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"assetId":"IMG_B"'),
      }),
    ));
    expect(screen.getByRole("button", { name: /select image 2/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Selected image 2.");
  });

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

function manySources(count = 17) {
  return Array.from({ length: count }, (_, i) => ({
    id: `S${i + 1}`,
    title: `Source ${i + 1}`,
    url: `https://example.com/${i + 1}`,
    snippet: `Snippet ${i + 1}`,
  }));
}

describe("research sources on a phone", () => {
  const originalInnerWidth = window.innerWidth;

  function setViewport(width: number) {
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: width });
    fireEvent(window, new Event("resize"));
  }

  afterEach(() => {
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: originalInnerWidth });
  });

  it("collapses the list to four cards and expands on demand", () => {
    setViewport(393);
    render(<GenericResultRenderer toolName="web_search" result={{ sources: manySources() }} />);

    expect(screen.getByText("17 attributed results")).toBeInTheDocument();
    expect(screen.getByText("Source 4")).toBeInTheDocument();
    expect(screen.queryByText("Source 5")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /show all 17 sources/i }));

    expect(screen.getByText("Source 17")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /show fewer sources/i })).toBeInTheDocument();
  });

  it("keeps the desktop layout showing every source with no expander", () => {
    setViewport(1280);
    render(<GenericResultRenderer toolName="web_search" result={{ sources: manySources() }} />);

    expect(screen.getByText("Source 17")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /show all 17 sources/i })).not.toBeInTheDocument();
  });
});

describe("document download card", () => {
  it("reports only the size the server actually measured", () => {
    const { rerender } = render(
      <GenericResultRenderer
        toolName="pdf_generate"
        result={{ title: "Field Report", filename: "report.pdf", downloadUrl: "/api/v1/generated-docs/D1", pageCount: 7, fileSizeKb: 248 }}
      />,
    );
    expect(screen.getByText("248 KB")).toBeInTheDocument();

    rerender(
      <GenericResultRenderer
        toolName="pdf_generate"
        result={{ title: "Field Report", filename: "report.pdf", downloadUrl: "/api/v1/generated-docs/D1" }}
      />,
    );
    expect(screen.queryByText(/KB$/)).not.toBeInTheDocument();
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });
});


describe("detailed research presentation", () => {
  it("renders a cited answer with readable findings and attributed source cards", () => {
    render(
      <GenericResultRenderer
        toolName="web_answer"
        result={{
          provider: "you.com",
          mode: "answer",
          content: "Gojo Satoru is a fictional character. [[1]]",
          sources: [
            {
              id: "Y1",
              title: "Character reference",
              url: "https://example.com/gojo",
              snippet: "A source-backed excerpt.",
            },
          ],
        }}
      />,
    );

    expect(screen.getByLabelText("Detailed research result")).toHaveTextContent("Cited answer");
    expect(screen.getByText("Gojo Satoru is a fictional character. [[1]]")).toBeInTheDocument();
    expect(screen.getByText("Character reference")).toBeInTheDocument();
    expect(screen.queryByText("web_answer result")).not.toBeInTheDocument();
  });
});
