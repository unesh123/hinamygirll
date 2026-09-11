/**
 * Autonomy behaviour for tool execution.
 *
 * These tests pin the consent contract:
 * - autonomy ON  → a proposed action uses standing consent, not a forged user approval
 * - autonomy OFF → nothing is executed until the user explicitly allows it
 *
 * The action is seeded through the persisted transcript so the controller sees a
 * restored assistant turn carrying tool requests on its first render.
 */

import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { ProviderRuntimeSelection } from "../providers/utils/resolveProviderSelection";
import { useCompanionController } from "./useCompanionController";

const plan: AssistantTurnPlan = {
  displayText: "Echoing that back for you.",
  spokenText: "Echoing that back for you.",
  language: "en-US",
  emotion: { primary: "thinking", intensity: 0.3, valence: 0.1, arousal: 0.1 },
  performance: { facePreset: "thinking", gesture: "explain", gazeTarget: "camera", headMotion: "subtle", blinkRate: 0.4 },
  memoryCandidates: [],
  toolRequests: [{ toolName: "diagnostic_echo", parameters: { message: "ok" } }],
};

const routing = {
  activeMode: "mock",
  useBackend: false,
} as unknown as ProviderRuntimeSelection;

function seedTranscriptWithProposedAction(): void {
  localStorage.setItem(
    "hinaa-messages-hinaa",
    JSON.stringify([
      {
        id: "assistant-with-action",
        role: "assistant",
        text: plan.displayText,
        createdAt: new Date().toISOString(),
        plan,
      },
    ]),
  );
}

function renderController(autoRunTools: boolean, conversationId?: string) {
  return renderHook(() =>
    useCompanionController({
      conversationId,
      routing,
      languagePolicy: "en-US",
      autoRunTools,
    }),
  );
}

describe("tool autonomy", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();
    seedTranscriptWithProposedAction();
    fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ status: "success", result: { echo: "ok" } }),
    }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("executes a proposed action without an approval click when autonomy is on", async () => {
    renderController(true);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/tools/execute");
    expect(JSON.parse(String(init.body))).toMatchObject({
      toolName: "diagnostic_echo",
      confirmed: true,
      approvalSource: "standing-consent",
    });
  });

  it("marks the action as running rather than awaiting approval when autonomy is on", async () => {
    const { result } = renderController(true);

    await waitFor(() => {
      const activity = result.current.messages.at(-1)?.toolActivity ?? [];
      expect(activity[0]?.status).toBe("running");
    });
  });

  it("does not execute anything while autonomy is off", async () => {
    const { result } = renderController(false);

    await waitFor(() => {
      const activity = result.current.messages.at(-1)?.toolActivity ?? [];
      expect(activity[0]?.status).toBe("pending");
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("still executes on explicit approval while autonomy is off", async () => {
    const { result } = renderController(false);

    await waitFor(() => {
      expect(result.current.messages.at(-1)?.toolActivity?.length).toBe(1);
    });
    expect(fetchMock).not.toHaveBeenCalled();

    await result.current.resolveToolRequest(
      "assistant-with-action",
      plan.toolRequests[0],
      true,
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      approvalSource: "user",
    });
  });

  it("does not submit a declined action", async () => {
    const { result } = renderController(false);

    await waitFor(() => {
      expect(result.current.messages.at(-1)?.toolActivity?.length).toBe(1);
    });

    await result.current.resolveToolRequest(
      "assistant-with-action",
      plan.toolRequests[0],
      false,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    await waitFor(() => {
      const activity = result.current.messages.at(-1)?.toolActivity ?? [];
      expect(activity[0]?.status).toBe("cancelled");
    });
  });

  it("does not execute the same proposed action twice under autonomy", async () => {
    const { rerender } = renderController(true);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    rerender();
    rerender();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("hydrates from the active conversation id instead of the legacy companion cache", () => {
    localStorage.setItem(
      "hinaa-messages-convo-1",
      JSON.stringify([
        {
          id: "conversation-message",
          role: "assistant",
          text: "This is the active conversation.",
          createdAt: new Date().toISOString(),
        },
      ]),
    );

    const { result } = renderController(false, "convo-1");

    expect(result.current.messages[0]?.id).toBe("conversation-message");
    expect(result.current.messages[0]?.text).toBe("This is the active conversation.");
  });

  it("starts a clean conversation when the active conversation id has no cached messages", () => {
    const { result } = renderController(false, "brand-new-convo");

    expect(result.current.messages[0]?.id).not.toBe("assistant-with-action");
    expect(result.current.messages[0]?.text).not.toBe(plan.displayText);
  });
});
