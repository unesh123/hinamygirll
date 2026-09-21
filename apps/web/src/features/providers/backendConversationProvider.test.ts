import { afterEach, describe, expect, it, vi } from "vitest";
import { BackendConversationProvider } from "./backendConversationProvider";
import { HINAA_DEV_USER } from "../../lib/hinaaIdentity";
import { buildMockPlan } from "./mockConversationProvider";

afterEach(() => vi.unstubAllGlobals());

describe("backend conversation provider", () => {
  it("parses NDJSON and validates the plan before yielding it", async () => {
    const plan = buildMockPlan("hello", "hinaa");
    const body = [
      JSON.stringify({ type: "thinking" }),
      JSON.stringify({
        type: "agent.step.started",
        runId: "run_1",
        stepId: "step_1",
        event: {
          sequence: 3,
          event_type: "agent.step.started",
          run_id: "run_1",
          step_id: "step_1",
          payload: { title: "Generate assistant response" },
        },
      }),
      JSON.stringify({ type: "text.delta", delta: "Namaste " }),
      JSON.stringify({ type: "plan", plan }),
      "",
    ].join("\n");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(body, {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson" },
        }),
      ),
    );
    const events = [];
    for await (const event of new BackendConversationProvider(
      "mock",
    ).streamTurn({
      text: "hello",
      companionId: "hinaa",
      signal: new AbortController().signal,
    }))
      events.push(event);
    expect(events.map((event) => event.type)).toEqual([
      "thinking",
      "agent.event",
      "text.delta",
      "plan",
    ]);
    expect(events[1]).toMatchObject({
      type: "agent.event",
      event: {
        event_type: "agent.step.started",
        run_id: "run_1",
        step_id: "step_1",
      },
    });
  });

  it("rejects a backend error event without exposing a vendor body", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            `${JSON.stringify({ type: "error", code: "PROVIDER_TIMEOUT", message: "Service timed out" })}\n`,
            { status: 200 },
          ),
        ),
    );
    const consume = async () => {
      for await (const _event of new BackendConversationProvider(
        "real",
      ).streamTurn({
        text: "hello",
        companionId: "hinaa",
        signal: new AbortController().signal,
      })) {
        // Consume the stream.
      }
    };
    await expect(consume()).rejects.toThrow(
      "PROVIDER_TIMEOUT: Service timed out",
    );
  });

  it("sends the selected response mode and omits it when unset", async () => {
    const body = `${JSON.stringify({ type: "plan", plan: buildMockPlan("hello", "hinaa") })}\n`;
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(body, {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const drain = async (request: Parameters<
      BackendConversationProvider["streamTurn"]
    >[0]) => {
      for await (const _event of new BackendConversationProvider(
        "claude",
      ).streamTurn(request)) {
        // Consume the stream.
      }
      return JSON.parse(fetchMock.mock.lastCall[1].body);
    };

    const explicit = await drain({
      text: "hello",
      companionId: "hinaa",
      signal: new AbortController().signal,
      language: "en-US",
      responseMode: "professional",
    });
    expect(explicit.responseMode).toBe("professional");

    const inferred = await drain({
      text: "hello",
      companionId: "hinaa",
      signal: new AbortController().signal,
      language: "en-US",
    });
    expect("responseMode" in inferred).toBe(false);
  });

  it("identifies the owner on the turn request", async () => {
    // The backend refuses anonymous private-data access, and turns are what
    // attach durable memory, so an unnamed request silently recalls nothing.
    const body = `${JSON.stringify({ type: "plan", plan: buildMockPlan("hello", "hinaa") })}\n`;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(body, {
        status: 200,
        headers: { "Content-Type": "application/x-ndjson" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const provider = new BackendConversationProvider("claude");
    for await (const _event of provider.streamTurn({
      text: "hello",
      companionId: "hinaa",
      signal: new AbortController().signal,
      language: "en-US",
    })) {
      // Consume the stream.
    }

    const headers = new Headers(fetchMock.mock.lastCall[1].headers);
    expect(headers.get("X-HINAA-Dev-User")).toBe(HINAA_DEV_USER);
  });
});
