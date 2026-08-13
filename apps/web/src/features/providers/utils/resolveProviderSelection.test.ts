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
  modelsByMode: Partial<Record<ProviderMode, string[]>> = {},
): ProvidersState {
  return {
    statuses: [],
    loaded: true,
    error: null,
    providerOptions: [],
    getModelOptions: (mode) => (modelsByMode[mode] ?? []).map((id, index) => ({
      id,
      label: id,
      isDefault: index === 0,
    })),
    getDefaultModel: (mode) => modelsByMode[mode]?.[0] ?? null,
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

  it("uses configured Claude as the automatic fallback after CX Gateway", () => {
    const preferences: ProviderPreferences = {
      preferredMode: "auto",
      preferredModelByProvider: { claude: "claude-sonnet-4-20250514" },
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith({ "cx-gateway": "unavailable", claude: "healthy", openai: "healthy", mock: "healthy" }),
    );

    expect(selection).toEqual({
      preferredMode: "auto",
      activeMode: "claude",
      activeModel: "claude-sonnet-4-20250514",
      reason: "automatic-fallback",
    });
  });

  it("replaces a stale Claude model with the refreshed gateway default", () => {
    const preferences: ProviderPreferences = {
      preferredMode: "claude",
      preferredModelByProvider: { claude: "claude-sonnet-4-20250514" },
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith(
        { claude: "healthy", mock: "healthy" },
        { claude: ["claude-sonnet-4-6", "claude-opus-4-6"] },
      ),
    );

    expect(selection.activeMode).toBe("claude");
    expect(selection.activeModel).toBe("claude-sonnet-4-6");
  });
});
