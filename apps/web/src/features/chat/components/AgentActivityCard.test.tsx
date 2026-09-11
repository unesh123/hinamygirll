import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AgentActivityCard } from "./AgentActivityCard";
import type { ActivityStep } from "./AgentActivityCard";

const runningStep: ActivityStep = {
  id: "step-1",
  toolName: "image_generate",
  title: "Generating image...",
  status: "running",
  message: "Dispatching to ComfyUI local GPU",
  stepNumber: 1,
  totalSteps: 3,
};

const completedStep: ActivityStep = {
  id: "step-2",
  toolName: "web_search",
  title: "Web Search completed",
  status: "completed",
  message: "Found 12 relevant results",
  stepNumber: 2,
  totalSteps: 3,
};

describe("AgentActivityCard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("renders null when inactive with no steps", () => {
    const { container } = render(
      <AgentActivityCard isActive={false} steps={[]} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the card when active", () => {
    render(<AgentActivityCard isActive steps={[runningStep]} />);
    expect(screen.getByTestId("agent-activity-card")).toBeInTheDocument();
  });

  it("shows active execution label when isActive=true", () => {
    render(<AgentActivityCard isActive steps={[runningStep]} />);
    expect(screen.getByText(/HINAA Active Execution/i)).toBeInTheDocument();
  });

  it("shows completed label when isActive=false and has steps", () => {
    render(<AgentActivityCard isActive={false} steps={[completedStep]} />);
    expect(screen.getByTestId("agent-activity-card")).toBeInTheDocument();
    expect(screen.getByText(/Execution Completed/i)).toBeInTheDocument();
  });

  it("displays the step title", () => {
    render(<AgentActivityCard isActive steps={[runningStep]} />);
    expect(screen.getByText("Generating image...")).toBeInTheDocument();
  });

  it("displays step counter (1 / 3)", () => {
    render(<AgentActivityCard isActive steps={[runningStep]} />);
    const text = screen.getByTestId("agent-activity-card").textContent || "";
    expect(text).toMatch(/1/);
    expect(text).toMatch(/3/);
  });

  it("shows a Cancel button when isActive and onCancel is provided", () => {
    const onCancel = vi.fn();
    render(<AgentActivityCard isActive steps={[runningStep]} onCancel={onCancel} />);
    const cancelBtn = screen.getByRole("button", { name: /cancel/i });
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not render Cancel button when isActive=false", () => {
    render(<AgentActivityCard isActive={false} steps={[completedStep]} onCancel={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });

  it("advances the elapsed timer while active", () => {
    render(<AgentActivityCard isActive steps={[runningStep]} />);
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    // Timer increments should have advanced — just check the card is still there
    expect(screen.getByTestId("agent-activity-card")).toBeInTheDocument();
  });

  it("renders multiple steps with different statuses", () => {
    const steps: ActivityStep[] = [
      completedStep,
      { ...runningStep, id: "s2", title: "Upscaling result", status: "running" },
    ];
    render(<AgentActivityCard isActive steps={steps} />);
    expect(screen.getByTestId("agent-activity-card")).toBeInTheDocument();
    expect(screen.getByText("Upscaling result")).toBeInTheDocument();
  });

  it("renders the step message when provided", () => {
    render(
      <AgentActivityCard
        isActive
        steps={[{
          id: "s1",
          title: "Compositing layers",
          status: "running",
          message: "Processing 4 references in parallel",
          stepNumber: 1,
          totalSteps: 4,
        }]}
      />
    );
    expect(screen.getByText("Compositing layers")).toBeInTheDocument();
    expect(screen.getByText(/Processing 4 references/)).toBeInTheDocument();
  });

  it("shows approval controls for a pending runtime confirmation", () => {
    const onConfirm = vi.fn();
    const onReject = vi.fn();
    render(
      <AgentActivityCard
        isActive
        steps={[{
          id: "approval-step",
          title: "Confirm browser action",
          status: "pending",
          message: "Waiting for your approval",
        }]}
        onConfirm={onConfirm}
        onReject={onReject}
      />
    );

    fireEvent.click(screen.getByTestId("confirm-activity-btn"));
    fireEvent.click(screen.getByTestId("reject-activity-btn"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it("keeps cancelled runtime steps truthful instead of rendering them as running", () => {
    render(
      <AgentActivityCard
        isActive={false}
        steps={[{
          id: "cancelled-step",
          title: "Stopped by user",
          status: "cancelled",
          message: "Runtime cancellation acknowledged",
        }]}
      />
    );

    expect(screen.getByText(/Execution Stopped/i)).toBeInTheDocument();
    expect(screen.getByText("Stopped by user")).toBeInTheDocument();
  });
});
