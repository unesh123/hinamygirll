import { afterEach, describe, expect, it, vi } from "vitest";
import { BackendConversationProvider } from "./backendConversationProvider";
import { buildMockPlan } from "./mockConversationProvider";

afterEach(() => vi.unstubAllGlobals());

describe("backend conversation provider", () => {
  it("parses NDJSON and validates the plan before yielding it", async () => {
    const plan = buildMockPlan("hello", "hinaa");
    const body = [
      JSON.stringify({ type: "thinking" }),
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
      "text.delta",
      "plan",
    ]);
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
});
