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
      providersLoaded: true,
      reason: "recovery",
    });
  });

  it("recovers a pinned CX Gateway to the live Claude brain", () => {
    // Health as measured from /api/v1/providers: the gateway has no credentials,
    // so a turn pinned to it would end in PROVIDER_CONFIGURATION_MISSING.
    const preferences: ProviderPreferences = {
      preferredMode: "cx-gateway",
      preferredModelByProvider: { "cx-gateway": "cx/gpt-5.6-sol" },
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith(
        { "cx-gateway": "unavailable", claude: "healthy", mock: "healthy" },
        { claude: ["claude-sonnet-4-6", "claude-opus-4-6"] },
      ),
    );

    expect(selection).toEqual({
      preferredMode: "cx-gateway",
      activeMode: "claude",
      activeModel: "claude-sonnet-4-6",
      providersLoaded: true,
      reason: "recovery",
    });
  });

  it("recovers a brain-rejected pin to the strongest live brain", () => {
    // The backend reports `claude` unavailable once a live call to its gateway
    // was rejected, so a turn still pinned to it must reach CodeCraft — the
    // frontier brain — rather than the flash-tier Gemini brain.
    const preferences: ProviderPreferences = {
      preferredMode: "claude",
      preferredModelByProvider: { claude: "claude-sonnet-4-6" },
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith(
        {
          claude: "unavailable",
          codecraft: "healthy",
          real: "healthy",
          mock: "healthy",
        },
        { codecraft: ["claude-fable-5"], real: ["gemini-3.5-flash-lite"] },
      ),
    );

    expect(selection).toEqual({
      preferredMode: "claude",
      activeMode: "codecraft",
      activeModel: "claude-fable-5",
      providersLoaded: true,
      reason: "recovery",
    });
  });

  it("recovers a rejected pin to the custom brain when it shares the live credential", () => {
    const preferences: ProviderPreferences = {
      preferredMode: "qwen",
      preferredModelByProvider: { qwen: "qwen3-coder" },
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith(
        { qwen: "unavailable", custom: "healthy", real: "healthy", mock: "healthy" },
        { custom: ["claude-fable-5"] },
      ),
    );

    expect(selection.activeMode).toBe("custom");
    expect(selection.activeModel).toBe("claude-fable-5");
  });

  it("lets auto skip a brain whose live calls were rejected", () => {
    const preferences: ProviderPreferences = {
      preferredMode: "auto",
      preferredModelByProvider: {},
    };

    const selection = resolveProviderSelection(
      preferences,
      providersWith(
        {
          "cx-gateway": "unavailable",
          claude: "unavailable",
          codecraft: "healthy",
          real: "healthy",
          mock: "healthy",
        },
        { codecraft: ["claude-fable-5"] },
      ),
    );

    expect(selection).toEqual({
      preferredMode: "auto",
      activeMode: "codecraft",
      activeModel: "claude-fable-5",
      providersLoaded: true,
      reason: "automatic-fallback",
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
      providersLoaded: true,
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
