import { describe, expect, it } from "vitest";
import {
  buildMockPlan,
  MockConversationProvider,
} from "./mockConversationProvider";

describe("MockConversationProvider", () => {
  it("returns the same validated plan for the same input", () => {
    expect(buildMockPlan("K gardai chau?", "hinaa")).toEqual(
      buildMockPlan("K gardai chau?", "hinaa"),
    );
  });

  it("selects bounded concerned performance for mood language", () => {
    const plan = buildMockPlan("Aaja mood ali off cha", "hinaa");
    expect(plan.emotion.primary).toBe("concerned");
    expect(plan.performance.gesture).toBe("reassure");
    expect(plan.toolRequests).toEqual([]);
  });

  it("streams deltas and a final plan without a network", async () => {
    const provider = new MockConversationProvider({ delayMs: 0 });
    const events = [];
    for await (const event of provider.streamTurn({
      text: "Namaste",
      companionId: "hiro",
      signal: new AbortController().signal,
      language: "en-US",
    })) {
      events.push(event);
    }
    expect(events[0]).toEqual({ type: "thinking" });
    expect(events.at(-1)?.type).toBe("plan");
    expect(events.some((event) => event.type === "text.delta")).toBe(true);
  });

  it("honors cancellation", async () => {
    const provider = new MockConversationProvider({ delayMs: 50 });
    const controller = new AbortController();
    const iterator = provider.streamTurn({
      text: "hello",
      companionId: "hinaa",
      signal: controller.signal,
      language: "en-US",
    });
    await iterator.next();
    controller.abort();
    await expect(iterator.next()).rejects.toMatchObject({ name: "AbortError" });
  });
});


describe("professional Demo guidance", () => {
  it("separates a detailed structured RSC explanation from concise plain speech", () => {
    const plan = buildMockPlan(
      "Explain React Server Components in detail with architecture, code, limitations, tests, and deployment.",
      "hinaa",
    );
    expect(plan.language).toBe("en-US");
    expect(plan.displayText).toContain("### Architecture");
    expect(plan.displayText).toContain("### Limitations and rules");
    expect(plan.displayText).toContain("```tsx");
    expect(plan.displayText).toContain("### Deployment");
    expect(plan.spokenText).not.toContain("#");
    expect(plan.spokenText.length).toBeLessThan(plan.displayText.length);
  });
});


describe("localized Demo guidance", () => {
  it("returns native-script Hindi and Nepali guidance with concise spoken summaries", () => {
    const hindi = buildMockPlan("हिना, मुझे ComfyUI setup समझाओ।", "hinaa", "hi-IN");
    expect(hindi.language).toBe("hi-IN");
    expect(hindi.displayText).toContain("ComfyUI सेटअप के लिए");
    expect(hindi.displayText).toContain("NVIDIA driver");
    expect(hindi.spokenText.length).toBeLessThan(hindi.displayText.length);

    const nepaliDisabled = buildMockPlan("हिना, मलाई ComfyUI को setup विस्तारमा बुझाऊ।", "hinaa", "hi-IN");
    expect(nepaliDisabled.language).toBe("hi-IN");
    expect(nepaliDisabled.displayText).toContain("Hindi और English");

    const nepali = buildMockPlan("हिना, मलाई ComfyUI को setup विस्तारमा बुझाऊ।", "hinaa", "ne-NP");
    expect(nepali.language).toBe("ne-NP");
    expect(nepali.displayText).toContain("ComfyUI को setup गर्न");
    expect(nepali.displayText).toContain("workflow queue गर्नुहोस्");
    expect(nepali.spokenText.length).toBeLessThan(nepali.displayText.length);
  });
});


describe("active Hindi language policy", () => {
  it("keeps normal Hindi Demo copy in Devanagari instead of Roman Hindi", () => {
    const plan = buildMockPlan("हिना, मेरी मदद करो।", "hinaa", "hi-IN");
    expect(plan.language).toBe("hi-IN");
    expect(plan.displayText).toMatch(/[\u0900-\u097F]/);
    expect(plan.displayText).not.toMatch(/Main abhi mock mode/i);
  });
});
