import { describe, expect, it } from "vitest";
import { realtimeGiveUpMessage } from "./useLiveConversation";

describe("realtimeGiveUpMessage", () => {
  it("names the hosting route when voice is aimed back at the same HTTPS origin", () => {
    const message = realtimeGiveUpMessage("wss://hinaa-workspace.vercel.app/api/v1/realtime", "hinaa-workspace.vercel.app");
    expect(message).toContain("hosting route does not carry voice connections");
    expect(message).not.toContain("after 10 attempts");
  });

  it("keeps the retry message for a real backend host", () => {
    const message = realtimeGiveUpMessage("wss://jade-wright.example.com/v1/realtime", "hinaa-workspace.vercel.app");
    expect(message).toBe("Realtime voice stopped retrying jade-wright.example.com after 10 attempts.");
  });
});
