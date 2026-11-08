import { useSyncExternalStore } from "react";
import { loadSettings, saveSettings } from "../features/settings/state/settingsStore";
import type { ThemePreference } from "../features/settings/types/settings";

export type ShellMode = "workspace" | "companion";
export type InspectorTab = "plan" | "tools" | "memory" | "integrations";
export type OrbStateName = "idle" | "listening" | "thinking" | "speaking";

export interface AgentStepView {
  id: string;
  label: string;
  status: string;
}

/** Snapshot the legacy conversation host publishes for shell chrome (orb, inspector, subtitles). */
export interface AgentSnapshot {
  state: OrbStateName;
  level: number;
  voiceActive: boolean;
  streamingText: string;
  lastText: string | null;
  steps: AgentStepView[];
  model: string | null;
}

export interface ShellState {
  mode: ShellMode;
  theme: ThemePreference;
  hosted: boolean;
  paletteOpen: boolean;
  inspectorOpen: boolean;
  inspectorTab: InspectorTab;
  agent: AgentSnapshot;
}

export const MODE_STORAGE_KEY = "hinaa-shell-mode";
export const MODE_PATHS: Record<ShellMode, string> = { workspace: "/workspace", companion: "/companion" };

const EMPTY_AGENT: AgentSnapshot = {
  state: "idle", level: 0, voiceActive: false, streamingText: "", lastText: null, steps: [], model: null,
};

function readMode(): ShellMode {
  try {
    return window.localStorage.getItem(MODE_STORAGE_KEY) === "companion" ? "companion" : "workspace";
  } catch {
    return "workspace";
  }
}

function readTheme(): ThemePreference {
  try {
    return loadSettings().appearance.theme;
  } catch {
    return "system";
  }
}

let state: ShellState = {
  mode: readMode(),
  theme: readTheme(),
  hosted: false,
  paletteOpen: false,
  inspectorOpen: false,
  inspectorTab: "plan",
  agent: EMPTY_AGENT,
};

const listeners = new Set<() => void>();

function set(patch: Partial<ShellState>): void {
  state = { ...state, ...patch };
  listeners.forEach((fn) => fn());
}

export function getShellState(): ShellState {
  return state;
}

export function subscribeShell(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useShell<T>(selector: (s: ShellState) => T): T {
  return useSyncExternalStore(subscribeShell, () => selector(state), () => selector(state));
}

export function resolveIsDark(theme: ThemePreference): boolean {
  if (theme === "system") return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? true;
  return theme === "dark";
}

export function applyThemeToDom(theme: ThemePreference): void {
  const dark = resolveIsDark(theme);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.classList.toggle("dark", dark);
}

export const shell = {
  setMode(mode: ShellMode): void {
    if (state.mode === mode) return;
    try { window.localStorage.setItem(MODE_STORAGE_KEY, mode); } catch { /* storage unavailable */ }
    set({ mode });
  },
  toggleMode(): ShellMode {
    const next: ShellMode = state.mode === "workspace" ? "companion" : "workspace";
    shell.setMode(next);
    return next;
  },
  /** Persist and apply a theme preference (shared with the legacy settings store). */
  setTheme(theme: ThemePreference): void {
    if (state.theme === theme) return;
    try {
      const current = loadSettings();
      saveSettings({ ...current, appearance: { ...current.appearance, theme } });
    } catch { /* storage unavailable */ }
    applyThemeToDom(theme);
    set({ theme });
  },
  /** Adopt a theme changed elsewhere (legacy settings UI) without writing it back. */
  adoptTheme(theme: ThemePreference): void {
    if (state.theme !== theme) set({ theme });
  },
  toggleTheme(): void {
    shell.setTheme(resolveIsDark(state.theme) ? "light" : "dark");
  },
  setHosted(hosted: boolean): void {
    if (state.hosted !== hosted) set({ hosted });
  },
  setPalette(open: boolean): void {
    if (state.paletteOpen !== open) set({ paletteOpen: open });
  },
  togglePalette(): void {
    set({ paletteOpen: !state.paletteOpen });
  },
  setInspector(open: boolean, tab?: InspectorTab): void {
    set({ inspectorOpen: open, inspectorTab: tab ?? state.inspectorTab });
  },
  publishAgent(agent: AgentSnapshot): void {
    const a = state.agent;
    if (
      a.state === agent.state && a.level === agent.level && a.voiceActive === agent.voiceActive &&
      a.streamingText === agent.streamingText && a.lastText === agent.lastText && a.model === agent.model &&
      a.steps.length === agent.steps.length && a.steps.every((s, i) => s.id === agent.steps[i].id && s.status === agent.steps[i].status)
    ) return;
    set({ agent });
  },
  /** Test helper: restore initial state. */
  reset(): void {
    state = { ...state, mode: readMode(), theme: readTheme(), hosted: false, paletteOpen: false, inspectorOpen: false, agent: EMPTY_AGENT };
    listeners.forEach((fn) => fn());
  },
};

/* ── Commands the legacy conversation host (App) implements ───────────── */

export type AppCommandName =
  | "new-chat" | "start-voice" | "stop-voice" | "open-settings" | "open-memory"
  | "open-terminal" | "open-showroom" | "toggle-history" | "open-projects" | "open-image-studio" | "open-models" | "open-operate" | "toggle-vision";

type AppCommandMap = Partial<Record<AppCommandName, () => void>>;

let handlers: AppCommandMap = {};
let pending: AppCommandName | null = null;

export function registerAppCommands(map: AppCommandMap): () => void {
  handlers = map;
  if (pending && handlers[pending]) {
    const name = pending;
    pending = null;
    queueMicrotask(() => handlers[name]?.());
  }
  return () => {
    if (handlers === map) handlers = {};
  };
}

/** Run a host command now, or as soon as the host mounts (e.g. after leaving a page route). */
export function runAppCommand(name: AppCommandName): void {
  const fn = handlers[name];
  if (fn) fn();
  else pending = name;
}
