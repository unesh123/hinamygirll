import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoopAgentRunPanel } from "./LoopAgentRunPanel";

// ── Agent run live feed ──
// The panel streams SSE turn events from the loop harness; the gate verdict
// ("gate PASSED") must be visible so the user sees why a run ended.

type Listener = (event: { type: string; data: string }) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, Listener[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    (this.listeners[type] ??= []).push(listener);
  }

  removeEventListener() {}

  close() {
    this.closed = true;
  }

  emit(type: string, data: unknown) {
    for (const listener of this.listeners[type] ?? []) {
      // Real frames carry the full envelope, like the API's SSE stream.
      listener({ type, data: JSON.stringify({ ts: new Date().toISOString(), event_type: type, data }) });
    }
  }
}

vi.stubGlobal("EventSource", MockEventSource);

describe("LoopAgentRunPanel", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("subscribes to the task SSE stream and renders the gate verdict", async () => {
    render(<LoopAgentRunPanel taskId="loop_test1" />);

    expect(MockEventSource.instances[0].url).toBe("/api/loop/events/loop_test1");

    const source = MockEventSource.instances[0];
    source.emit("turn_verified", { turn: 0, passed: true, exit_code: 0, command: "true" });
    source.emit("loop_finished", { status: "COMPLETED", summary: "done", total_turns: 0 });

    await waitFor(() => {
      expect(screen.getByText(/gate PASSED/)).toBeInTheDocument();
      expect(screen.getByText(/turn verified/)).toBeInTheDocument();
      expect(screen.getByText(/loop finished/)).toBeInTheDocument();
    });
  });

  it("renders a failed gate in red wording", async () => {
    render(<LoopAgentRunPanel taskId="loop_test2" />);

    const source = MockEventSource.instances[0];
    source.emit("turn_verified", { turn: 1, passed: false, exit_code: 2, command: "cat missing.txt" });
    source.emit("loop_failed", { status: "FAILED", summary: "gate failed" });

    await waitFor(() => {
      expect(screen.getByText(/gate FAILED/)).toBeInTheDocument();
    });
  });
});
