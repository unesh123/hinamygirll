/**
 * settings feature — public exports.
 * Import from this barrel, not from internal paths.
 */

export { SettingsTrigger } from "./components/SettingsTrigger";
export { SettingsDialog } from "./components/SettingsDialog";
export { SettingsV6 } from "./SettingsV6";
export { useSettings } from "./hooks/useSettings";
export { useSettingsPersistence } from "./hooks/useSettingsPersistence";
export type { HinaaSettings, AppearanceSettings, ProviderPreferences } from "./types/settings";
