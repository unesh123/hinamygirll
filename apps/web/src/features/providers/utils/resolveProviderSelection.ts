/**
 * resolveProviderSelection.ts
 *
 * Implements the automatic provider routing policy.
 */
import type { ProviderHealth, ProviderMode, ProvidersState } from "../types/provider";
import type { ProviderPreferences } from "../../settings/types/settings";

export type ConcreteProviderMode = Exclude<ProviderMode, "auto">;

export interface ProviderRuntimeSelection {
  preferredMode: ProviderMode | "auto";
  activeMode: ConcreteProviderMode | null;
  activeModel: string | null;
  /** Whether provider health has finished loading from the backend. */
  providersLoaded: boolean;
  reason:
    | "explicit-user-choice"
    | "automatic-primary"
    | "automatic-fallback"
    | "recovery"
    | "providers-loading"
    | null;
}

/**
 * Voice route selects STT, Brain, and TTS independently.
 * A single "activeMode" conflates capabilities that may use different providers.
 */
export type VoiceRoute = {
  sttProvider: "elevenlabs" | "deepgram" | "browser";
  brainProvider: "claude" | "cx" | "qwen" | "openai" | "gemini";
  ttsProvider: "elevenlabs" | "azure" | "browser";
  ready: boolean;
};

/**
 * Resolve a voice route from current provider health.
 * STT, Brain, and TTS are selected independently so a provider
 * outage in one capability does not silently disable the others.
 */
export function resolveVoiceRoute(
  providers: ProvidersState,
): VoiceRoute {
  // Service-level providers (elevenlabs, deepgram, azure-speech) live in
  // the statuses array with string IDs; ProviderMode covers brain modes.
  const health = (id: string): string =>
    providers.statuses.find((s) => s.id === id)?.state ?? "unknown";

  const sttProvider: VoiceRoute["sttProvider"] =
    health("elevenlabs") === "healthy" ? "elevenlabs"
    : health("deepgram") === "healthy" ? "deepgram"
    : "browser";
  const brainProvider: VoiceRoute["brainProvider"] =
    providers.getHealth("real") === "healthy" ? "gemini"
    : providers.getHealth("cx-gateway") === "healthy" ? "cx"
    : providers.getHealth("claude") === "healthy" ? "claude"
    : providers.getHealth("qwen") === "healthy" ? "qwen"
    : providers.getHealth("openai") === "healthy" ? "openai"
    : "gemini";
  const ttsProvider: VoiceRoute["ttsProvider"] =
    health("elevenlabs") === "healthy" ? "elevenlabs"
    : health("azure-speech") === "healthy" ? "azure"
    : "browser";
  return {
    sttProvider,
    brainProvider,
    ttsProvider,
    ready: providers.loaded,
  };
}

/**
 * Ranked by answer quality. Health comes from /api/v1/providers, which reports
 * what live calls proved, so a brain its gateway rejects is skipped outright.
 */
const AUTO_PRIORITY: ConcreteProviderMode[] = [
  "cx-gateway",
  "claude",
  "codecraft",
  "custom",
  "real",
  "qwen",
  "openai",
  "agent-router",
  "ollama",
  "local",
  "mock",
];

/**
 * Brains that answer from this app's own process. They always report healthy,
 * so they must be judged last — otherwise the zero-credit stand-in wins every
 * automatic turn simply because no gateway has been measured yet.
 */
const IN_PROCESS_MODES: ConcreteProviderMode[] = ["local", "mock"];

/**
 * Strongest brain to send the next turn to.
 *
 * Proven first: a real gateway whose last live call answered outranks anything
 * else. The untested pass exists for the honest state the backend reports after
 * a restart, when credentials exist but nothing has been watched answering —
 * those brains still deserve the turn that proves them. The in-process brains
 * come last, as the genuine fallback rather than the default.
 */
function firstUsableMode(
  providers: ProvidersState,
): ConcreteProviderMode | null {
  const pick = (accept: (health: ProviderHealth, mode: ConcreteProviderMode) => boolean) => {
    for (const mode of AUTO_PRIORITY) {
      if (accept(providers.getHealth(mode), mode)) return mode;
    }
    return null;
  };
  const isNotInProcess = (mode: ConcreteProviderMode) => !IN_PROCESS_MODES.includes(mode);

  return (
    pick((health, mode) => isNotInProcess(mode) && health === "healthy")
    ?? pick((health, mode) => isNotInProcess(mode) && health === "untested")
    ?? pick((health) => health === "healthy")
  );
}

export interface RecoveryBrain {
  mode: ConcreteProviderMode;
  model: string | null;
}

/**
 * The brain a "switch to a working model" button may honestly name.
 *
 * Only `healthy` qualifies — the state the backend gives a gateway after a live
 * call answered through it. A brain that is merely configured, untested, or
 * already refused this credential stays out of the list, so the button can never
 * move him from one broken brain to another and still claim it works. Null means
 * nothing measured is left to switch to, and the caller must say so instead of
 * offering a canned model id.
 */
export function pickRecoveryBrain(providers: ProvidersState): RecoveryBrain | null {
  if (!providers.loaded) return null;
  for (const mode of AUTO_PRIORITY) {
    if (IN_PROCESS_MODES.includes(mode)) continue;
    if (providers.getHealth(mode) !== "healthy") continue;
    return { mode, model: providers.getDefaultModel(mode) };
  }
  return null;
}

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

    // Preferences are persisted locally, so a saved provider may no longer be
    // reachable on this deployment. Recover to another real brain instead of
    // surfacing a provider-configuration error in chat.
    if (providers.loaded && (health === "unavailable" || health === "disabled")) {
      // Recover to the strongest brain `auto` would have chosen (the same
      // capability order, proven gateways before merely configured ones)
      // instead of the canned mock responder, so a persisted-but-now-unreachable
      // provider still answers with a genuine model. Mock remains the last resort.
      const recoveryMode: ConcreteProviderMode =
        firstUsableMode(providers) ?? "mock";
      const recoveryModel =
        recoveryMode !== "mock"
          ? resolveCurrentModel(
              recoveryMode,
              models[recoveryMode as keyof typeof models],
              providers,
            )
          : null;
      return {
        preferredMode,
        activeMode: recoveryMode,
        activeModel: recoveryModel,
        providersLoaded: true,
        reason: "recovery",
      };
    }

    return {
      preferredMode,
      activeMode: concrete,
      activeModel: explicitModel,
      providersLoaded: providers.loaded,
      reason: "explicit-user-choice",
    };
  }

  // 2. Automatic selection — only after providers have loaded
  if (providers.loaded) {
    const selected = firstUsableMode(providers);
    if (selected !== null) {
      const model = resolveCurrentModel(
        selected,
        models[selected as keyof typeof models],
        providers,
      );
      return {
        preferredMode: "auto",
        activeMode: selected,
        activeModel: model,
        providersLoaded: true,
        reason: selected === AUTO_PRIORITY[0] ? "automatic-primary" : "automatic-fallback",
      };
    }
  }

  // 3. Providers still loading — never silently fall to mock
  if (!providers.loaded) {
    return {
      preferredMode: "auto",
      activeMode: null,
      activeModel: null,
      providersLoaded: false,
      reason: "providers-loading",
    };
  }

  // 4. Complete outage / all providers explicitly unavailable
  return {
    preferredMode: "auto",
    activeMode: "mock",
    activeModel: null,
    providersLoaded: true,
    reason: "automatic-fallback",
  };
}
