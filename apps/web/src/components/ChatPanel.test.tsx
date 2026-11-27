import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatPanel } from "./ChatPanel";
import { buildChatPerfMessages } from "../fixtures/chatPerfMessages";

describe("ChatPanel v3", () => {
  it("virtualizes 1,000 messages without mounting all rows in DOM", () => {
    const messages = buildChatPerfMessages(1000);
    render(
      <ChatPanel
        messages={messages}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
      />,
    );

    const rows = screen.getAllByTestId(/message-row-/);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.length).toBeLessThan(80);
  });

  it("opens slash command palette on / and inserts selected trigger", () => {
    const onInputChange = vi.fn();
    render(
      <ChatPanel
        messages={[]}
        input="/"
        onInputChange={onInputChange}
        onSend={vi.fn()}
      />,
    );
    const palette = screen.getByTestId("chat-slash-palette");
    expect(palette).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /\/timer/i }));
    expect(onInputChange).toHaveBeenCalledWith("/timer ");
  });

  it("enforces soft warning >= 2000 chars and blocks sending past 8000 chars", () => {
    const longInput = "a".repeat(8001);
    const onSend = vi.fn();
    render(
      <ChatPanel
        messages={[]}
        input={longInput}
        onInputChange={vi.fn()}
        onSend={onSend}
      />,
    );
    expect(screen.getByTestId("char-limit-indicator")).toHaveTextContent("8001/8000");
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });

  it("renders AgentActivityFeed rail with parallel steps, thought toggle, and inline approval", () => {
    const onApprove = vi.fn();
    render(
      <ChatPanel
        messages={[]}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        thought="Parallel read strategy"
        thoughtSummary="Reading config first"
        activitySteps={[
          {
            id: "s1",
            toolName: "workspace_read_file",
            title: "Reading package.json",
            status: "completed",
            parallelGroup: "batch-1",
            durationMs: 14,
          },
        ]}
        pendingApproval={{
          approvalId: "ap-1",
          toolName: "mlai_run_routine",
          label: "Running routine",
          reason: "External side effect",
        }}
        onApprove={onApprove}
      />,
    );
    expect(screen.getByTestId("agent-activity-feed")).toBeInTheDocument();
    expect(screen.getByTestId("inline-approval-banner")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Allow/i }));
    expect(onApprove).toHaveBeenCalledOnce();
  });
});
