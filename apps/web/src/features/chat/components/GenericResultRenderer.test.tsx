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
  it("renders an applied code patch with the unified diff and its backup trail", () => {
    const diff = [
      "--- a/services.py",
      "+++ b/services.py",
      "@@ -1,3 +1,3 @@",
      "-    return 1",
      "+    return 2",
    ].join("\n");
    render(
      <GenericResultRenderer
        toolName="code_patch"
        result={{
          status: "success",
          data: {
            file: "apps/api/hinaa_api/services.py",
            diff,
            bytesChanged: 1,
            backup: "/home/u/.hinaa/workspace/code-backups/2026_services.py",
          },
        }}
      />,
    );
    expect(screen.getByText(/patch applied/i)).toBeInTheDocument();
    expect(screen.getByText(/return 2/)).toHaveStyle({ color: "rgb(134, 239, 172)" });
    expect(screen.getByText(/return 1/)).toHaveStyle({ color: "rgb(252, 165, 165)" });
    expect(screen.getByText("2026_services.py")).toBeInTheDocument();
  });

  it("keeps a refused workspace path visible as a typed error, not a silent card", () => {
    render(
      <GenericResultRenderer
        toolName="code_read"
        result={{ status: "error", error: "That path is treated as secret and is off-limits to HINAA.", code: "CODE_PATH_REFUSED" }}
      />,
    );
    expect(screen.getByText(/off-limits to HINAA/)).toBeInTheDocument();
  });

  it("shows an approved command run with its exit chip and tailed output marker", () => {
    render(
      <GenericResultRenderer
        toolName="terminal_run"
        result={{
          status: "success",
          data: {
            command: "python -m pytest tests -q",
            cwd: ".",
            exitCode: 1,
            stdout: "2 failed, 26 passed",
            stderr: "",
            truncated: true,
            timedOut: false,
            durationMs: 4310,
          },
        }}
      />,
    );
    expect(screen.getByText(/exit 1/)).toBeInTheDocument();
    expect(screen.getByText("2 failed, 26 passed")).toBeInTheDocument();
    expect(screen.getByText(/output tailed/)).toBeInTheDocument();
  });

  it("surfaces a refused command as its typed reason, never as a blank card", () => {
    render(
      <GenericResultRenderer
        toolName="terminal_run"
        result={{ status: "error", error: "'rm' is on the refused list — it can escape the workspace jail or wreck the machine.", code: "TERMINAL_COMMAND_REFUSED" }}
      />,
    );
    expect(screen.getByText(/refused list/)).toBeInTheDocument();
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
