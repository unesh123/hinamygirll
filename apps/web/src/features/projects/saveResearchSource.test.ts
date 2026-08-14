import { describe, expect, it } from "vitest";
import { collectResearchSources } from "./saveResearchSource";

describe("collectResearchSources", () => {
  it("keeps attributable successful research sources, derives domains, and removes duplicates or errors", () => {
    const sources = collectResearchSources([
      {
        toolName: "web_search",
        result: {
          data: {
            sources: [
              { id: "a", title: "Primary guide", url: "https://www.example.test/guide", snippet: "First result" },
              { id: "dup", title: "Duplicate", url: "https://www.example.test/guide", snippet: "Duplicate result" },
              { id: "private", title: "Private", url: "file:///local-only", snippet: "Must not render" },
            ],
          },
        },
      },
      {
        toolName: "web_research",
        result: { status: "error", data: { sources: [{ title: "Failed", url: "https://failed.test", snippet: "No" }] } },
      },
      {
        toolName: "image_search",
        result: { data: { sources: [{ title: "Wrong tool", url: "https://ignored.test", snippet: "No" }] } },
      },
    ]);

    expect(sources).toEqual([
      expect.objectContaining({
        id: "a",
        title: "Primary guide",
        url: "https://www.example.test/guide",
        domain: "example.test",
        index: 0,
      }),
    ]);
  });
});
