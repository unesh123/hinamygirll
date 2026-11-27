import { describe, expect, it, vi } from "vitest";
import { BackendConversationProvider } from "./backendConversationProvider";

describe("BackendConversationProvider agentic SSE events", () => {
  it("forwards agenticMode and normalizes top-level tool and confirmation events", async () => {
    const encoder = new TextEncoder();
    const ndjson = [
      JSON.stringify({ type: "agentic.started", correlationId: "run-9", goal: "Build HTML + MP4" }),
      JSON.stringify({ type: "agent.step.started", correlationId: "run-9", step: 1, maxSteps: 6 }),
      JSON.stringify({ type: "tool.started", correlationId: "run-9", step: 1, toolName: "workspace_write_file" }),
      JSON.stringify({ type: "tool.completed", correlationId: "run-9", step: 1, toolName: "workspace_write_file", durationMs: 12 }),
      JSON.stringify({
        type: "confirmation.required",
        correlationId: "run-9",
        approval_id: "appr-1",
        tool: "mlai_run_routine",
        arguments_hash: "hash1234",
        reason: "Needs approval",
      }),
      JSON.stringify({
        type: "plan",
        plan: {
          schemaVersion: 1,
          spokenText: "Done",
          displayText: "Done",
          language: "en-US",
          emotion: { primary: "neutral", intensity: 0.4, valence: 0.5, arousal: 0.3 },
          performance: { facePreset: "neutral", gesture: "none", gazeTarget: "camera", headMotion: "none", blinkRate: 0.5 },
          memoryCandidates: [],
          toolRequests: [],
        },
      }),
    ].join("\n") + "\n";

    let capturedBody: Record<string, unknown> = {};
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url, init) => {
        capturedBody = JSON.parse(String((init as RequestInit)?.body || "{}"));
        return new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(ndjson));
              controller.close();
            },
          }),
          { status: 200, headers: { "Content-Type": "application/x-ndjson" } },
        );
      }),
    );

    try {
      const prov = new BackendConversationProvider("real");
      const out = [];
      for await (const ev of prov.streamTurn({
        text: "Build page",
        companionId: "hinaa",
        language: "en-US",
        agenticMode: true,
        signal: new AbortController().signal,
      })) {
        out.push(ev);
      }

      expect(capturedBody.agenticMode).toBe(true);
      const agentEvents = out.filter((e) => e.type === "agent.event");
      expect(agentEvents.map((e: any) => e.event.event_type)).toEqual([
        "agentic.started",
        "agent.step.started",
        "tool.started",
        "tool.completed",
        "confirmation.required",
      ]);
      const conf = agentEvents[4] as any;
      expect(conf.event.payload.arguments_hash).toBe("hash1234");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("aborts cleanly with TurnFailure when a stream stalls past the idle timeout", async () => {
    const encoder = new TextEncoder();
    let cancelled = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(`${JSON.stringify({ type: "agentic.started", correlationId: "run-stall" })}\n`));
              // Intentionally never enqueue more chunks or close
            },
            cancel() {
              cancelled = true;
            },
          }),
          { status: 200, headers: { "Content-Type": "application/x-ndjson" } },
        ),
      ),
    );

    try {
      const prov = new BackendConversationProvider("real", { streamIdleTimeoutMs: 40 });
      const seen = [];
      let caught: any;
      try {
        for await (const ev of prov.streamTurn({
          text: "Render typography MP4",
          companionId: "hinaa",
          language: "en-US",
          agenticMode: true,
          signal: new AbortController().signal,
        })) {
          seen.push(ev);
        }
      } catch (err) {
        caught = err;
      }
      expect(seen.map((e) => e.type)).toEqual(["agent.event"]);
      expect(caught).toBeDefined();
      expect(caught.code).toBe("PROVIDER_UNAVAILABLE");
      expect(caught.retryable).toBe(true);
      expect(cancelled).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
