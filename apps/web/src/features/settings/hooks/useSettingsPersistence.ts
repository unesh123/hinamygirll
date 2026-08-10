/**
 * useSettingsPersistence — applies settings side-effects to the DOM.
 *
 * Theme:
 *   "system" → remove data-theme (CSS media query handles it)
 *   "light"  → data-theme="light"
 *   "dark"   → data-theme="dark"  (default, already set by theme-sync script)
 *
 * Motion:
 *   "system"  → remove data-reduced-motion (respect OS)
 *   "full"    → data-reduced-motion="false"
 *   "reduced" → data-reduced-motion="true"
 *
 * Called once at App root with current settings. Safe to re-run on every change.
 */

import { useEffect } from "react";
import type { HinaaSettings } from "../types/settings";

export function useSettingsPersistence(settings: HinaaSettings): void {
  // ── Theme ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    const { theme } = settings.appearance;
    if (theme === "system") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", theme);
    }
  }, [settings.appearance.theme]);

  // ── Motion ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    const { motion } = settings.appearance;
    if (motion === "system") {
      // Let OS prefers-reduced-motion control behaviour — remove override
      document.documentElement.removeAttribute("data-reduced-motion");
    } else {
      document.documentElement.setAttribute(
        "data-reduced-motion",
        motion === "reduced" ? "true" : "false",
      );
    }
  }, [settings.appearance.motion]);
}
