import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { parseResponseBlocks } from "./ResponseBlock";
import { ResponseRenderer } from "./ResponseRenderer";

describe("ResponseRenderer & ResponseBlock", () => {
  it("parses and renders plain markdown text blocks", () => {
    render(<ResponseRenderer content="Hello **world** from HINAA" />);
    expect(screen.getByText("world").tagName).toBe("STRONG");
  });

  it("parses fenced code blocks and alerts into discrete AST blocks", () => {
    const raw = `Here is the explanation:
\`\`\`python
def greet():
    return "hi"
\`\`\`
> [!WARNING]
> Please do not share API keys.`;

    const blocks = parseResponseBlocks(raw);
    expect(blocks).toHaveLength(3);
    expect(blocks[0].kind).toBe("text");
    expect(blocks[1].kind).toBe("code");
    expect(blocks[2].kind).toBe("warning");

    render(<ResponseRenderer content={blocks} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Please do not share API keys.");
    expect(screen.getByLabelText("Code block")).toBeInTheDocument();
  });

  it("renders terminal, progress, and error blocks cleanly", () => {
    render(
      <ResponseRenderer
        content={[
          {
            kind: "terminal",
            command: "pnpm test",
            output: "292 passed",
            exitCode: 0,
          },
          {
            kind: "progress",
            percentage: 75,
            message: "Ingesting files",
          },
          {
            kind: "error",
            code: "ERR_TIMEOUT",
            message: "Connection timed out",
          },
        ]}
      />
    );

    expect(screen.getByText("$ pnpm test")).toBeInTheDocument();
    expect(screen.getByText("exit 0")).toBeInTheDocument();
    expect(screen.getByText("Ingesting files")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Connection timed out");
  });

  it("parses and renders AST v2 callouts, quotes, and collapsible blocks", () => {
    const raw = `> [!NOTE] Architecture Note
> This system uses three-tier caching.

> [!TIP]
> Use keyboard shortcut Ctrl+K to open search.

> Simplicity is the prerequisite for reliability.

<details>
<summary>Deep Details</summary>
Internal pipeline steps are configured here.
</details>`;

    const blocks = parseResponseBlocks(raw);
    expect(blocks.some((b) => b.kind === "callout" && b.calloutType === "note")).toBe(true);
    expect(blocks.some((b) => b.kind === "callout" && b.calloutType === "tip")).toBe(true);
    expect(blocks.some((b) => b.kind === "quote")).toBe(true);
    expect(blocks.some((b) => b.kind === "collapsible")).toBe(true);

    render(<ResponseRenderer content={blocks} />);
    expect(screen.getByText("This system uses three-tier caching.")).toBeInTheDocument();
    expect(screen.getByText("Simplicity is the prerequisite for reliability.")).toBeInTheDocument();
    expect(screen.getByText("Deep Details")).toBeInTheDocument();
  });

  it("renders interactive action cards, steps, and status badges", () => {
    const onAction = vi.fn();
    render(
      <ResponseRenderer
        onActionClick={onAction}
        content={[
          {
            kind: "status",
            status: "running",
            label: "Verifying tests",
            details: "309 tests passing",
          },
          {
            kind: "steps",
            steps: [
              { title: "Initialize Sandbox", status: "completed" },
              { title: "Run Migrations", status: "running" },
              { title: "Start Gateway", status: "pending" },
            ],
          },
          {
            kind: "action_card",
            title: "Deployment Action",
            description: "Ready to deploy to staging?",
            actions: [
              { label: "Deploy Now", actionId: "act-deploy", primary: true },
              { label: "Cancel", actionId: "act-cancel" },
            ],
          },
        ]}
      />
    );

    expect(screen.getByText("Verifying tests")).toBeInTheDocument();
    expect(screen.getByText("Initialize Sandbox")).toBeInTheDocument();
    expect(screen.getByText("Run Migrations")).toBeInTheDocument();

    const deployBtn = screen.getByRole("button", { name: "Deploy Now" });
    fireEvent.click(deployBtn);
    expect(onAction).toHaveBeenCalledWith("act-deploy");
  });
});
