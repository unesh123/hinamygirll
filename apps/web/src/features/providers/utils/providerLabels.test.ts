import { describe, expect, it } from "vitest";
import { buildProviderOptions, providerModeFromId } from "./providerLabels";

describe("provider discovery", () => {
  it("converts discovery IDs to backend request modes", () => {
    expect(providerModeFromId("gemini")).toBe("real");
    expect(providerModeFromId("experiential")).toBe("experiential");
    expect(providerModeFromId("unsupported-research-lane")).toBeNull();
  });
  it("offers Groq and Experiential when the backend reports them", () => {
    const options = buildProviderOptions([
      { id: "groq", state: "healthy", capabilities: ["llm"] },
      { id: "experiential", state: "untested", capabilities: ["llm"] },
      { id: "local", state: "degraded", capabilities: ["llm"] },
      { id: "tinyfish", state: "healthy", capabilities: ["search"] },
    ]);
    expect(options.filter((p) => p.available).map((p) => p.mode)).toEqual(["mock", "local", "groq", "experiential"]);
  });

  it("keeps unavailable gateways discoverable without allowing selection", () => {
    const exp = buildProviderOptions([
      { id: "experiential", state: "unavailable", capabilities: [], userMessage: "Key missing" },
    ]).find((p) => p.mode === "experiential");
    expect(exp).toMatchObject({ available: false, healthReason: "Key missing" });
  });
});
