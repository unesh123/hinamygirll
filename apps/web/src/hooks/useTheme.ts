import { useCallback, useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const HINA_THEME_STORAGE_KEY = "hina.theme";
const LEGACY_THEME_STORAGE_KEY = "hinaa-theme";

function readInitialTheme(): ThemePreference {
  if (typeof window === "undefined") return "system";
  try {
    const raw =
      window.localStorage.getItem(HINA_THEME_STORAGE_KEY) ??
      window.localStorage.getItem(LEGACY_THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") return raw;
  } catch {
    // ignore storage access errors
  }
  return "system";
}

function getSystemDark(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function resolveTheme(pref: ThemePreference, systemPrefersDark = getSystemDark()): ResolvedTheme {
  if (pref === "dark") return "dark";
  if (pref === "light") return "light";
  return systemPrefersDark ? "dark" : "light";
}

export function useTheme(initialOverride?: ThemePreference) {
  const [theme, setThemeState] = useState<ThemePreference>(
    () => initialOverride ?? readInitialTheme(),
  );
  const [systemDark, setSystemDark] = useState<boolean>(() => getSystemDark());

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    setSystemDark(mq.matches);
    mq.addEventListener?.("change", listener);
    return () => mq.removeEventListener?.("change", listener);
  }, []);

  const resolvedTheme = resolveTheme(theme, systemDark);
  const isDark = resolvedTheme === "dark";

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);

  const setTheme = useCallback((next: ThemePreference) => {
    setThemeState(next);
    try {
      window.localStorage.setItem(HINA_THEME_STORAGE_KEY, next);
      if (next === "light" || next === "dark") {
        window.localStorage.setItem(LEGACY_THEME_STORAGE_KEY, next);
      }
    } catch {
      // ignore storage failure
    }
  }, []);

  const toggle = useCallback(() => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  }, [resolvedTheme, setTheme]);

  return {
    theme,
    resolvedTheme,
    isDark,
    setTheme,
    toggle,
  };
}
