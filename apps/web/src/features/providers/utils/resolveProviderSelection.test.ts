import { describe, expect, it } from "vitest";
import type { ProviderPreferences } from "../../settings/types/settings";
import type {
  ProviderHealth,
  ProviderMode,
  ProvidersState,
} from "../types/provider";
import { resolveProviderSelection } from "./resolveProviderSelection";

function providersWith(
  healthByMode: Partial<Record<ProviderMode, ProviderHealth>>,
): ProvidersState {
  return {
    statuses: [],
    loaded: true,
    error: null,
    providerOptions: [],
    getModelOptions: () => [],
    getDefaultModel: () => null,
    getHealth: (mode) => healthByMode[mode] ?? "unknown",
    refresh: () => undefined,
  };
}

describe("resolveProviderSelection", () => {
  it("recovers from an unavailable persisted provider to mock mode", () => {
    const preferences: ProviderPreferences = {
      preferredMode: "cx-gateway",
      preferredModelByProvider: { "cx-gateway": "cx/gpt-5.6-sol" },
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith({ "cx-gateway": "unavailable", mock: "healthy" }),
    );

    expect(selection).toEqual({
      preferredMode: "cx-gateway",
      activeMode: "mock",
      activeModel: null,
      reason: "recovery",
    });
  });

  it("keeps an available explicit selection intact", () => {
    const preferences: ProviderPreferences = {
      preferredMode: "openai",
      preferredModelByProvider: { openai: "gpt-5-mini" },
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith({ openai: "healthy", mock: "healthy" }),
    );

    expect(selection.activeMode).toBe("openai");
    expect(selection.activeModel).toBe("gpt-5-mini");
    expect(selection.reason).toBe("explicit-user-choice");
  });
});
