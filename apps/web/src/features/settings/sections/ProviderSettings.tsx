/**
 * ProviderSettings — provider and model selection.
 *
 * Displays:
 * - Provider mode select (Automatic, Custom Gateway, OpenAI, Gemini, Local, Demo)
 * - Live health status for selected provider
 * - Current active provider when Automatic is selected
 * - Model selector (preserves per-provider preference)
 * - Degraded/unavailable reason when present
 * - Manual refresh control
 *
 * Internal mode names (e.g. "real") are never shown in the UI.
 */

import {
  SettingsRow,
  SettingsSection,
  SettingsSelect,
  SettingsStatus,
} from "../components/SettingsPrimitives";
import type { ProvidersState } from "../../providers/types/provider";
import type { ModelByProvider, ProviderPreferenceMode, ProviderPreferences } from "../types/settings";
import styles from "./ProviderSettings.module.css";

interface Props {
  provider: ProviderPreferences;
  providers: ProvidersState;
  onChange: (patch: Partial<ProviderPreferences>) => void;
  /** Currently resolved provider when mode is "auto" */
  activeMode?: Exclude<ProviderPreferenceMode, "auto"> | null;
}

// User-facing labels — internal keys never shown in UI
const MODE_LABELS: Record<ProviderPreferenceMode, string> = {
  auto:   "Automatic",
  custom: "Custom Gateway",
  openai: "OpenAI",
  real:   "Gemini",
  local:  "Local",
  mock:   "Demo",
  claude: "Claude",
  qwen: "Qwen",
  "agent-router": "Agent Router (agentrouter.org)",
  "cx-gateway":   "CX Gateway (cx/gpt-5.6-sol)",
  "gemini-live":  "Gemini Live (Native Speech-to-Speech)",
};

const MODE_DESCRIPTIONS: Record<ProviderPreferenceMode, string> = {
  auto:   "HINAA picks the best available provider.",
  custom: "Your private backend gateway (hcnsec.cn).",
  openai: "GPT models via OpenAI.",
  real:   "Google Gemini models.",
  local:  "Zero-credit on-device model. Text only.",
  mock:   "Deterministic demo. No API calls.",
  claude: "Claude via HINAA’s own Anthropic-compatible API configuration.",
  qwen: "QwenCloud text brain via HINAA’s private local backend; ElevenLabs continues to provide Hinaa’s voice.",
  "agent-router": "agentrouter.org — access Claude, GPT, DeepSeek and more with your $175 credits.",
  "cx-gateway":   "cx/gpt-5.6-sol — your premium Cloudflare gateway.",
  "gemini-live":  "Google Gemini Live Bidi S2S (<300ms native multimodal audio).",
};

export function ProviderSettings({ provider, providers, onChange, activeMode }: Props) {
  const { providerOptions, getModelOptions, loaded } = providers;
  const elevenLabs = providers.statuses.find((status) => status.id === "elevenlabs");
  const cloudVoiceReady = elevenLabs?.state === "healthy" || elevenLabs?.state === "degraded";

  // Build mode select options
  const modeOptions = [
    { value: "auto", label: "Automatic", disabled: false },
    ...providerOptions.map((opt) => ({
      value: opt.mode,
      label: opt.label + (!opt.available ? " — Unavailable" : ""),
      disabled: !opt.available,
    })),
  ];

  // Health of the selected mode (or resolved active mode for auto)
  const displayMode = provider.preferredMode === "auto"
    ? (activeMode ?? null)
    : provider.preferredMode;

  const currentHealth = displayMode
    ? providers.getHealth(displayMode as Parameters<typeof providers.getHealth>[0])
    : loaded ? "healthy" : "checking";

  // Model options for the current concrete mode
  const modelOptions = displayMode ? getModelOptions(displayMode as Parameters<typeof providers.getModelOptions>[0]) : [];
  const hasModels = modelOptions.length > 0;

  // Current saved model for this provider (null = automatic)
  const currentModel =
    displayMode && provider.preferredMode !== "auto"
      ? (provider.preferredModelByProvider[provider.preferredMode] ?? "")
      : "";

  // Description for selected mode
  const description = MODE_DESCRIPTIONS[provider.preferredMode];

  const handleModeChange = (mode: string) => {
    onChange({ preferredMode: mode as ProviderPreferenceMode });
    // Do NOT reset model preferences for other providers
  };

  const handleModelChange = (model: string) => {
    if (provider.preferredMode === "auto") return;
    const newModelByProvider: ModelByProvider = {
      ...provider.preferredModelByProvider,
      [provider.preferredMode]: model || null,
    };
    onChange({ preferredModelByProvider: newModelByProvider });
  };

  // Validate stored model still exists in available options
  const isModelValid =
    !currentModel ||
    modelOptions.some((m) => m.id === currentModel);

  const modelSelectValue = isModelValid ? currentModel : "";

  return (
    <SettingsSection label="AI Provider" divider>
      <SettingsRow
        label="Provider"
        description={description}
        htmlFor="settings-provider-mode"
      >
        <SettingsSelect
          id="settings-provider-mode"
          value={provider.preferredMode}
          options={!loaded ? [{ value: provider.preferredMode, label: "Checking…" }] : modeOptions}
          onChange={handleModeChange}
          disabled={!loaded}
          aria-label="AI provider"
        />
      </SettingsRow>

      <SettingsRow
        label="Voice replies"
        description={
          cloudVoiceReady
            ? "ElevenLabs is available for Hinaa’s cloud voice."
            : "Hinaa speaks through your device voice when cloud voice is unavailable. Add ELEVENLABS_API_KEY and ELEVENLABS_HINAA_VOICE_ID only in the local backend environment to enable the cloud voice."
        }
      >
        <span className={styles.activeLabel} aria-live="polite">
          {cloudVoiceReady ? "ElevenLabs voice ready" : "Device voice fallback"}
        </span>
      </SettingsRow>

      {/* Health status row */}
      <div className={styles.statusRow}>
        <SettingsStatus health={currentHealth} />

        {provider.preferredMode === "auto" && activeMode && (
          <span className={styles.activeLabel}>
            Using {MODE_LABELS[activeMode]}
          </span>
        )}

        {providers.error && (
          <p className={styles.errorNote} role="alert">
            {providers.error}
          </p>
        )}

        {displayMode && !isModelValid && (
          <p className={styles.warningNote}>
            Previously selected model is no longer available. Using automatic.
          </p>
        )}
      </div>

      {/* Model selector — only for concrete provider with models */}
      {hasModels && provider.preferredMode !== "auto" && (
        <SettingsRow
          label="Model"
          description="Specific model, or Automatic."
          htmlFor="settings-model"
        >
          <SettingsSelect
            id="settings-model"
            value={modelSelectValue}
            options={[
              { value: "", label: "Automatic" },
              ...modelOptions.map((m) => ({
                value: m.id,
                label: m.id,
              })),
            ]}
            onChange={handleModelChange}
            aria-label="AI model"
          />
        </SettingsRow>
      )}

    </SettingsSection>
  );
}
