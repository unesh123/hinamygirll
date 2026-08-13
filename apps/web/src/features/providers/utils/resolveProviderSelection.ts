/**
 * resolveProviderSelection.ts
 *
 * Implements the automatic provider routing policy.
 */
import type { ProviderMode, ProvidersState } from "../types/provider";
import type { ProviderPreferences } from "../../settings/types/settings";

export type ConcreteProviderMode = Exclude<ProviderMode, "auto">;

export interface ProviderRuntimeSelection {
  preferredMode: ProviderMode | "auto";
  activeMode: ConcreteProviderMode | null;
  activeModel: string | null;
  reason:
    | "explicit-user-choice"
    | "automatic-primary"
    | "automatic-fallback"
    | "recovery"
    | null;
}

const AUTO_PRIORITY: ConcreteProviderMode[] = [
  "cx-gateway",
  "claude",
  "real",
  "openai",
  "custom",
  "agent-router",
  "local",
  "mock",
];

function resolveCurrentModel(
  mode: ConcreteProviderMode,
  savedModel: string | null | undefined,
  providers: ProvidersState,
): string | null {
  const options = providers.getModelOptions(mode);
  // An empty catalog means the status fetch has not supplied model metadata;
  // preserve an explicit choice until a real catalog is available.
  if (savedModel && (!providers.loaded || options.length === 0 || options.some((option) => option.id === savedModel))) {
    return savedModel;
  }
  return providers.getDefaultModel(mode) || null;
}

/**
 * Resolves the currently selected provider/model preferences into a concrete
 * provider choice for the next chat request.
 */
export function resolveProviderSelection(
  preferences: ProviderPreferences,
  providers: ProvidersState
): ProviderRuntimeSelection {
  const { preferredMode, preferredModelByProvider: models = {} } = preferences || {};

  // 1. Explicit selection
  if (preferredMode !== "auto") {
    const concrete = preferredMode as ConcreteProviderMode;
    const health = providers.getHealth(concrete);
    const explicitModel = resolveCurrentModel(
      concrete,
      models[concrete as keyof typeof models],
      providers,
    );

    // Preferences are persisted locally. If a saved paid or custom provider is
    // no longer configured on this deployment, recover to deterministic mock
    // mode rather than surfacing a provider-configuration error in chat.
    if (providers.loaded && (health === "unavailable" || health === "disabled")) {
      return {
        preferredMode,
        activeMode: "mock",
        activeModel: null,
        reason: "recovery",
      };
    }

    return {
      preferredMode,
      activeMode: concrete,
      activeModel: explicitModel,
      reason: "explicit-user-choice",
    };
  }

  // 2. Automatic selection
  for (const mode of AUTO_PRIORITY) {
    if (providers.getHealth(mode) === "healthy") {
      const model = resolveCurrentModel(
        mode,
        models[mode as keyof typeof models],
        providers,
      );
      return {
        preferredMode: "auto",
        activeMode: mode,
        activeModel: model,
        reason: mode === AUTO_PRIORITY[0] ? "automatic-primary" : "automatic-fallback",
      };
    }
  }

  // 3. Complete outage / nothing healthy
  // Fall back to mock if literally everything else is down
  return {
    preferredMode: "auto",
    activeMode: "mock",
    activeModel: null,
    reason: "automatic-fallback",
  };
}
