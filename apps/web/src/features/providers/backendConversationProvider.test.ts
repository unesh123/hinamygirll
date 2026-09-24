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

  it("rejects a backend error event with a human line, keeping the code for routing", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            `${JSON.stringify({ type: "error", code: "PROVIDER_TIMEOUT", message: "Service timed out", retryable: true })}\n`,
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
    const failure = await consume().catch((error) => error);
    expect(failure.message).toBe(
      "The selected brain did not answer before the live safety timeout.",
    );
    expect(failure.code).toBe("PROVIDER_TIMEOUT");
    expect(failure.retryable).toBe(true);
  });

  it("collapses an edge error page into one line", async () => {
    const cloudflarePage = [
      "<!DOCTYPE html>",
      '<html><head><title>502: Bad gateway</title></head>',
      "<body><h1>Error 502: Bad gateway</h1><p>The origin web server does not return a valid response.</p></body></html>",
    ].join("\n");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(cloudflarePage, {
          status: 502,
          statusText: "Bad Gateway",
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
      ),
    );
    const consume = async () => {
      for await (const _event of new BackendConversationProvider(
        "claude",
      ).streamTurn({
        text: "hello",
        companionId: "hinaa",
        signal: new AbortController().signal,
      })) {
        // Consume the stream.
      }
    };
    const failure = await consume().catch((error) => error);
    expect(failure.status).toBe(502);
    expect(failure.message).toContain("502");
    expect(failure.message).not.toContain("<");
    expect(failure.message.split("\n")).toHaveLength(1);
  });

  it("refuses a 200 whose body is an edge error page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html><body>Gateway Timeout</body></html>", {
          status: 200,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );
    const consume = async () => {
      for await (const _event of new BackendConversationProvider(
        "claude",
      ).streamTurn({
        text: "hello",
        companionId: "hinaa",
        signal: new AbortController().signal,
      })) {
        // Consume the stream.
      }
    };
    const failure = await consume().catch((error) => error);
    expect(failure.message).not.toContain("<");
    expect(failure.message).toContain("200");
  });

  it("reports a mid-stream non-JSON line without quoting it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          `${JSON.stringify({ type: "thinking" })}\n<tr><td>upstream broke off here</td></tr>\n`,
          { status: 200, headers: { "Content-Type": "application/x-ndjson" } },
        ),
      ),
    );
    const consume = async () => {
      const seen = [];
      for await (const event of new BackendConversationProvider(
        "claude",
      ).streamTurn({
        text: "hello",
        companionId: "hinaa",
        signal: new AbortController().signal,
      })) {
        seen.push(event);
      }
      return seen;
    };
    const failure = await consume().catch((error) => error);
    expect(failure.message).not.toContain("upstream broke off here");
    expect(failure.message).toContain("200");
    expect(failure.message.split("\n")).toHaveLength(1);
    expect(failure.message.length).toBeGreaterThan(0);
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
