import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { GoalsDashboard } from "./GoalsDashboard";

describe("GoalsDashboard with Loop Engine and Evals", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the header and both tab options", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/goals/self-model")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            entity: "Hina",
            version: "1.0",
            sentient: false,
            has_human_consciousness: false,
            capabilities: {},
            unavailable_capabilities: [],
            limitations: [],
          }),
        });
      }
      if (url.includes("/api/evals/latest")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            total_cases: 11,
            passed_cases: 11,
            overall_score: 100.0,
            pass_rate: 100.0,
            category_scores: {
              safety_guardrails: 100.0,
              tool_selection: 100.0,
              loop_verification: 100.0,
              multilingual: 100.0,
            },
            duration_ms: 15,
            timestamp: new Date().toISOString(),
          }),
        });
      }
      if (url.includes("/api/goals")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
        });
      }
      if (url.includes("/api/loop/tasks")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            tasks: [
              {
                task_id: "loop_test_123",
                goal_title: "Autonomous CI Gate Loop",
                status: "COMPLETED",
                updated_at: new Date().toISOString(),
                total_receipts: 2,
              },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as any;

    render(<GoalsDashboard />);

    expect(screen.getByText(/Autonomous Goal Planner & Loop Engine/i)).toBeInTheDocument();
    expect(screen.getByText(/Multi-Stage Goals & DAG/i)).toBeInTheDocument();
    expect(screen.getByText(/Loop Engine \(sorrycc Autonomous Harness\)/i)).toBeInTheDocument();
  });

  it("switches to the Loop Engine tab and displays the 3 Iron Rules and Eval Scorecard", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/evals/latest")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            total_cases: 11,
            passed_cases: 11,
            overall_score: 100.0,
            pass_rate: 100.0,
            category_scores: {
              safety_guardrails: 100.0,
              tool_selection: 100.0,
              loop_verification: 100.0,
              multilingual: 100.0,
            },
            duration_ms: 15,
            timestamp: new Date().toISOString(),
          }),
        });
      }
      if (url.includes("/api/loop/tasks")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            tasks: [
              {
                task_id: "loop_test_123",
                goal_title: "Autonomous CI Gate Loop",
                status: "COMPLETED",
                updated_at: new Date().toISOString(),
                total_receipts: 2,
              },
            ],
          }),
        });
      }
      if (url.includes("/api/loop/status/loop_test_123")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            task_id: "loop_test_123",
            goal_title: "Autonomous CI Gate Loop",
            description: "Verifies test passing",
            status: "COMPLETED",
            total_turns: 2,
            receipts: [
              {
                turn: 1,
                timestamp: new Date().toISOString(),
                exit_code: 0,
                passed: true,
                duration_ms: 120,
                command: ["python", "-m", "pytest"],
                diff_stat: "1 file changed",
                stdout_snippet: "2 passed in 0.12s",
              },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }) as any;

    render(<GoalsDashboard />);

    const loopTabBtn = screen.getByText(/Loop Engine \(sorrycc Autonomous Harness\)/i);
    fireEvent.click(loopTabBtn);

    // Verify 3 Iron Rules
    expect(screen.getByText(/1\. 上限看模型，下限看架构/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Done 是声明，不是证明/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Agent 会忘，repo 不会/i)).toBeInTheDocument();

    // Verify Scorecard
    await waitFor(() => {
      expect(screen.getByText(/Automated Agent Reasoning & Benchmark Scorecard/i)).toBeInTheDocument();
      expect(screen.getByText(/Safety Guardrails:/i)).toBeInTheDocument();
      expect(screen.getByText(/Tool Selection:/i)).toBeInTheDocument();
      expect(screen.getByText(/Loop Verification:/i)).toBeInTheDocument();
      expect(screen.getByText(/Multilingual & Nepali:/i)).toBeInTheDocument();
    });

    // Verify Loop Task (match in both list and detail)
    await waitFor(() => {
      expect(screen.getAllByText(/Autonomous CI Gate Loop/i).length).toBeGreaterThan(0);
    });
  });
});
