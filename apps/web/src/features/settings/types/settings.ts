/**
 * HinaaSettings — typed, versioned settings model.
 *
 * Rules:
 * - Increment SETTINGS_VERSION when adding breaking changes
 * - Use parseStoredSettings → migrateSettings → validateSettings → mergeWithDefaults pipeline
 * - Never store provider-health state
 * - Never store active fallback provider
 * - Never store credentials
 * - Only add settings for behaviour that genuinely exists today
 *
 * Version 4 — fluent Hindi (Devanagari) and English are the only active HINAA
 * language routes. Older experimental Nepali selections migrate to auto Hindi/English.
 */

export const SETTINGS_VERSION = 4 as const;
export const SETTINGS_KEY = "hinaa_settings_v1" as const;

export type ThemePreference = "system" | "light" | "dark";
export type MotionPreference = "system" | "full" | "reduced";

/**
 * Avatar rendering style.
 * - "auto": try the VRM 3D model, fall back to the procedural 2D avatar.
 * - "vrm": always use the 3D model (falls back if no model is available).
 * - "procedural": always use the procedural 2D avatar.
 */
export type AvatarStylePreference = "auto" | "vrm" | "procedural";

export interface AppearanceSettings {
  theme: ThemePreference;
  /** "system" = respect prefers-reduced-motion OS setting. */
  motion: MotionPreference;
  avatarVisible: boolean;
  avatarStyle: AvatarStylePreference;
}

/** Provider modes supported by the backend. */
export type ProviderPreferenceMode =
  | "auto"
  | "custom"
  | "openai"
  | "real"
  | "local"
  | "mock"
  | "claude"
  | "agent-router"
  | "cx-gateway"
  | "gemini-live";

/** Saved model selection per provider. Null = automatic. */
export type ModelByProvider = Partial<
  Record<Exclude<ProviderPreferenceMode, "auto">, string | null>
>;

export interface ProviderPreferences {
  /** User's preferred provider — "auto" defers to routing policy. */
  preferredMode: ProviderPreferenceMode;
  /** Model preference scoped per provider — not reset when switching providers. */
  preferredModelByProvider: ModelByProvider;
}

export type ActiveLanguagePolicy = "auto-hi-en" | "hi-IN" | "en-US";

export interface LanguageSettings {
  /** HINAA responds in automatic Hindi-English, fixed Devanagari Hindi, or fixed English. */
  activePolicy: ActiveLanguagePolicy;
}

export interface HinaaSettings {
  _version: typeof SETTINGS_VERSION;
  appearance: AppearanceSettings;
  provider: ProviderPreferences;
  language: LanguageSettings;
}

// ── Defaults ──────────────────────────────────────────────────────────────────

export const DEFAULT_SETTINGS: HinaaSettings = {
  _version: SETTINGS_VERSION,
  appearance: {
    theme: "system",
    motion: "system",
    avatarVisible: true,
    avatarStyle: "auto",
  },
  provider: {
    preferredMode: "cx-gateway",
    preferredModelByProvider: {},
  },
  language: {
    activePolicy: "auto-hi-en",
  },
};
