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
    const applyTheme = (isDark: boolean) => {
      document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
      if (isDark) {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    };

    if (theme === "system") {
      const media = window.matchMedia?.("(prefers-color-scheme: dark)");
      applyTheme(Boolean(media?.matches));
      const listener = (e: MediaQueryListEvent) => applyTheme(e.matches);
      media?.addEventListener?.("change", listener);
      return () => media?.removeEventListener?.("change", listener);
    } else {
      applyTheme(theme === "dark");
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
