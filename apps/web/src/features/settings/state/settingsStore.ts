/**
 * settingsStore — localStorage persistence with 4-step validation pipeline.
 *
 * Pipeline: parseStoredSettings → migrateSettings → validateSettings → mergeWithDefaults
 *
 * Rules:
 * - Parse errors on a single field do not discard the whole object
 * - Unknown keys are ignored (forward compatibility)
 * - Old versions are migrated
 * - Version from the future uses defaults for unknown keys
 * - Never store health state, active fallback, or credentials
 * - Handles unavailable localStorage (quota exceeded, private mode restrictions)
 * - Does not write on every render — caller must explicitly call saveSettings
 */

import {
  DEFAULT_SETTINGS,
  SETTINGS_KEY,
  SETTINGS_VERSION,
  type ActiveLanguagePolicy,
  type AppearanceSettings,
  type AvatarStylePreference,
  type HinaaSettings,
  type ModelByProvider,
  type MotionPreference,
  type ProviderPreferenceMode,
  type ProviderPreferences,
  type ThemePreference,
} from "../types/settings";

// ── Guard helpers ─────────────────────────────────────────────────────────────

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function safeString<T extends string>(
  v: unknown,
  allowed: readonly T[],
  fallback: T,
): T {
  return allowed.includes(v as T) ? (v as T) : fallback;
}

function safeBoolean(v: unknown, fallback: boolean): boolean {
  return typeof v === "boolean" ? v : fallback;
}

// ── Step 1: parseStoredSettings ───────────────────────────────────────────────
// Extract raw JSON from localStorage. Returns null on any error.

function parseStoredSettings(): Record<string, unknown> | null {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

// ── Step 2: migrateSettings ───────────────────────────────────────────────────
// Transform old schema versions to the current shape.

function migrateSettings(raw: Record<string, unknown>): Record<string, unknown> {
  const version = raw._version;

  if (version === SETTINGS_VERSION) {
    return raw; // current version, no migration needed
  }

  if (typeof version !== "number" || version > SETTINGS_VERSION) {
    // Future or unknown version — return as-is and let validateSettings fill gaps
    return raw;
  }

  const migrated = { ...raw };
  if (version < 2) {
    const provider = isObject(raw.provider) ? { ...raw.provider } : {};
    // CX becomes the default for fresh and previously automatic installs. An
    // explicit provider choice remains untouched, and runtime routing still
    // falls back safely when CX is not configured on this local machine.
    if (provider.preferredMode === undefined || provider.preferredMode === "auto") {
      provider.preferredMode = "cx-gateway";
    }
    migrated.provider = provider;
  }
  if (version < 3) {
    migrated.language = { activePolicy: "auto-hi-en" };
  }
  migrated._version = SETTINGS_VERSION;
  return migrated;
}

// ── Step 3: validateSettings ──────────────────────────────────────────────────
// Validate each field individually. Malformed field → use default for that field.
// Valid fields from a partially broken object are preserved.

function validateAppearance(raw: unknown): AppearanceSettings {
  const d = DEFAULT_SETTINGS.appearance;
  const obj = isObject(raw) ? raw : {};

  return {
    theme: safeString<ThemePreference>(obj.theme, ["system", "light", "dark"], d.theme),
    motion: safeString<MotionPreference>(obj.motion, ["system", "full", "reduced"], d.motion),
    avatarVisible: safeBoolean(obj.avatarVisible, d.avatarVisible),
    avatarStyle: safeString<AvatarStylePreference>(
      obj.avatarStyle,
      ["auto", "vrm", "procedural"],
      d.avatarStyle,
    ),
  };
}

function validateModelByProvider(raw: unknown): ModelByProvider {
  if (!isObject(raw)) return {};
  const allowed: Array<Exclude<ProviderPreferenceMode, "auto">> = [
    "custom", "openai", "real", "local", "mock", "agent-router", "cx-gateway", "gemini-live",
  ];
  const result: ModelByProvider = {};
  for (const key of allowed) {
    const v = raw[key];
    if (typeof v === "string" || v === null) {
      result[key] = v;
    }
    // else: malformed entry — skip it (leaves key absent, treated as null at read time)
  }
  return result;
}

function validateProvider(raw: unknown): ProviderPreferences {
  const d = DEFAULT_SETTINGS.provider;
  const obj = isObject(raw) ? raw : {};

  return {
    preferredMode: safeString<ProviderPreferenceMode>(
      obj.preferredMode,
      ["auto", "custom", "openai", "real", "local", "mock", "agent-router", "cx-gateway", "gemini-live"],
      d.preferredMode,
    ),
    preferredModelByProvider: validateModelByProvider(obj.preferredModelByProvider),
  };
}

function validateLanguage(raw: unknown): HinaaSettings["language"] {
  const obj = isObject(raw) ? raw : {};
  return {
    activePolicy: safeString<ActiveLanguagePolicy>(
      obj.activePolicy,
      ["auto-hi-en", "hi-IN", "en-US", "ne-NP-experimental"],
      DEFAULT_SETTINGS.language.activePolicy,
    ),
  };
}

function validateSettings(raw: Record<string, unknown>): HinaaSettings {
  return {
    _version: SETTINGS_VERSION,
    appearance: validateAppearance(raw.appearance),
    provider: validateProvider(raw.provider),
    language: validateLanguage(raw.language),
  };
}

// ── Step 4: mergeWithDefaults ─────────────────────────────────────────────────
// Fills any missing top-level sections with defaults.
// (validateSettings already fills missing fields, so this is a safety net.)

function mergeWithDefaults(validated: HinaaSettings): HinaaSettings {
  return {
    ...DEFAULT_SETTINGS,
    ...validated,
    appearance: { ...DEFAULT_SETTINGS.appearance, ...validated.appearance },
    provider: { ...DEFAULT_SETTINGS.provider, ...validated.provider },
    language: { ...DEFAULT_SETTINGS.language, ...validated.language },
  };
}

// ── Public API ────────────────────────────────────────────────────────────────

/** Load, migrate, validate, and merge settings from localStorage. */
export function loadSettings(): HinaaSettings {
  const raw = parseStoredSettings();
  if (!raw) return { ...DEFAULT_SETTINGS };

  const migrated = migrateSettings(raw);
  const validated = validateSettings(migrated);
  return mergeWithDefaults(validated);
}

/** Persist settings to localStorage. Silently handles storage errors. */
export function saveSettings(settings: HinaaSettings): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (err) {
    // Quota exceeded or private mode restriction — app continues normally
    console.warn("[settings] localStorage unavailable:", err);
  }
}
