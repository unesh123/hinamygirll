import { describe, expect, it } from "vitest";
import { createInitialAgentTurnState, reduceAgentTurnEvent } from "./agentEvents";

describe("reduceAgentTurnEvent", () => {
  it("tracks parallel tool groups, human labels, thought deltas, artifacts, and completion", () => {
    let state = createInitialAgentTurnState();
    state = reduceAgentTurnEvent(state, { type: "turn.started", turnId: "run-1", route: "coding", at: 100 });
    expect(state.phase).toBe("thinking");
    expect(state.route).toBe("coding");

    state = reduceAgentTurnEvent(state, { type: "thought.delta", text: "Inspecting workspace config" }, 110);
    expect(state.thought).toBe("Inspecting workspace config");

    state = reduceAgentTurnEvent(
      state,
      { type: "tool.started", step: 1, toolName: "workspace_read_file", label: "Reading", target: "package.json", lane: "files", parallelGroup: "batch-1" },
      120,
    );
    state = reduceAgentTurnEvent(
      state,
      { type: "tool.started", step: 1, toolName: "web_search", label: "Searching web", target: "vitest virtual", lane: "research", parallelGroup: "batch-1" },
      125,
    );
    expect(state.phase).toBe("executing");
    expect(state.steps).toHaveLength(2);
    expect(state.steps[0].title).toBe("Reading package.json");
    expect(state.steps[0].parallelGroup).toBe("batch-1");

    state = reduceAgentTurnEvent(state, { type: "tool.completed", step: 1, toolName: "workspace_read_file", durationMs: 42 }, 162);
    expect(state.steps[0].status).toBe("completed");
    expect(state.steps[0].durationMs).toBe(42);
    expect(state.steps[1].status).toBe("running");

    state = reduceAgentTurnEvent(
      state,
      { type: "artifact.ready", artifact: { kind: "video", filePath: "output/clip.mp4", download_url: "/files/clip.mp4" } },
      180,
    );
    expect(state.artifacts).toHaveLength(1);
    expect(state.artifacts[0].label).toBe("clip.mp4");

    state = reduceAgentTurnEvent(state, { type: "turn.done" }, 200);
    expect(state.phase).toBe("done");
    expect(state.finishedAt).toBe(200);
  });

  it("handles approval.required cleanly", () => {
    let state = createInitialAgentTurnState();
    state = reduceAgentTurnEvent(
      state,
      { type: "confirmation.required", approval_id: "a-1", tool: "mlai_run_routine", label: "Running routine", reason: "External effect" },
      300,
    );
    expect(state.phase).toBe("awaiting_approval");
    expect(state.pendingApproval?.approvalId).toBe("a-1");
    expect(state.pendingApproval?.toolName).toBe("mlai_run_routine");
  });
});
