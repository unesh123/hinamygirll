/**
 * The history sent with a turn is the model's whole memory of the conversation.
 * It must be the live transcript (not a snapshot from an earlier render), and a
 * regenerate/edit must send exactly the truncated transcript it resends from.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildMockPlan } from "../providers/mockConversationProvider";
import type { ProviderRuntimeSelection } from "../providers/utils/resolveProviderSelection";
import { useCompanionController } from "./useCompanionController";

const routing = { activeMode: "claude", useBackend: true } as unknown as ProviderRuntimeSelection;

type StreamBody = { text: string; history?: Array<{ role: string; content: string }> };

function replyStream(reply: string): Response {
  const plan = buildMockPlan(reply, "hinaa");
  plan.displayText = reply;
  plan.spokenText = reply;
  const lines = [{ type: "text.delta", delta: reply }, { type: "plan", plan }];
  return new Response(lines.map((line) => `${JSON.stringify(line)}\n`).join(""), {
    headers: { "Content-Type": "application/x-ndjson" },
  });
}

describe("conversation history sent with each turn", () => {
  let turnBodies: StreamBody[];

  beforeEach(() => {
    localStorage.clear();
    turnBodies = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/conversations/turns:stream")) {
          const body = JSON.parse(String(init?.body)) as StreamBody;
          turnBodies.push(body);
          return replyStream(`Reply to ${body.text}.`);
        }
        return Response.json({}, { status: 404 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function renderController() {
    return renderHook(() => useCompanionController({ routing, languagePolicy: "en-US" }));
  }

  it("includes the previous exchange in the next turn", async () => {
    const { result } = renderController();
    await act(async () => {
      await result.current.sendText("first question");
    });
    await act(async () => {
      await result.current.sendText("second question");
    });

    expect(turnBodies).toHaveLength(2);
    expect(turnBodies[1].history).toEqual(
      expect.arrayContaining([
        { role: "user", content: "first question" },
        { role: "assistant", content: "Reply to first question." },
      ]),
    );
  });

  it("resends from a truncated transcript and replaces what follows it", async () => {
    const { result } = renderController();
    await act(async () => {
      await result.current.sendText("original");
    });
    const greetingOnly = result.current.messages.slice(0, 1);

    await act(async () => {
      await result.current.sendText("edited", { historyBase: greetingOnly });
    });

    expect(turnBodies[1].history).toEqual([{ role: "assistant", content: greetingOnly[0].text }]);
    await waitFor(() => {
      expect(result.current.messages.map((message) => message.text)).toEqual([
        greetingOnly[0].text,
        "edited",
        "Reply to edited.",
      ]);
    });
  });

  it("sends an explicitly empty history when resending the very first message", async () => {
    const { result } = renderController();
    await act(async () => {
      await result.current.sendText("again", { historyBase: [] });
    });
    expect(turnBodies[0].history).toEqual([]);
  });
});
