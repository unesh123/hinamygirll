/**
 * useSettings — React hook for reading and updating HinaaSettings.
 *
 * - Loads from localStorage on first render (safe — returns defaults on error)
 * - Updates are partial and type-safe via named section helpers
 * - Persists on each update using settingsStore.saveSettings
 * - Cross-tab sync via the storage event
 * - Does not write on every render — only on explicit updates
 */

import { useCallback, useEffect, useState } from "react";
import { loadSettings, saveSettings } from "../state/settingsStore";
import { DEFAULT_SETTINGS } from "../types/settings";
import type {
  AppearanceSettings,
  HinaaSettings,
  LanguageSettings,
  ProviderPreferences,
} from "../types/settings";

export interface UseSettingsReturn {
  settings: HinaaSettings;
  setAppearance: (patch: Partial<AppearanceSettings>) => void;
  setLanguage: (patch: Partial<LanguageSettings>) => void;
  setProvider: (patch: Partial<ProviderPreferences>) => void;
  resetToDefaults: () => void;
}

export function useSettings(): UseSettingsReturn {
  const [settings, setSettings] = useState<HinaaSettings>(() => loadSettings());

  // Cross-tab sync: when another tab writes settings, update this tab
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === "hinaa_settings_v1" && e.newValue) {
        try {
          // Reload from storage (goes through validation)
          setSettings(loadSettings());
        } catch {
          // Ignore parse errors from other tabs
        }
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const setAppearance = useCallback((patch: Partial<AppearanceSettings>) => {
    setSettings((current) => {
      const next: HinaaSettings = {
        ...current,
        appearance: { ...current.appearance, ...patch },
      };
      saveSettings(next);
      return next;
    });
  }, []);

  const setLanguage = useCallback((patch: Partial<LanguageSettings>) => {
    setSettings((current) => {
      const next: HinaaSettings = {
        ...current,
        language: { ...current.language, ...patch },
      };
      saveSettings(next);
      return next;
    });
  }, []);

  const setProvider = useCallback((patch: Partial<ProviderPreferences>) => {
    setSettings((current) => {
      const next: HinaaSettings = {
        ...current,
        provider: { ...current.provider, ...patch },
      };
      saveSettings(next);
      return next;
    });
  }, []);

  const resetToDefaults = useCallback(() => {
    const next = { ...DEFAULT_SETTINGS };
    saveSettings(next);
    setSettings(next);
  }, []);

  return { settings, setAppearance, setLanguage, setProvider, resetToDefaults };
}
