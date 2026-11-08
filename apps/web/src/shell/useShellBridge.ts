import { useEffect, useRef } from "react";
import type { ThemePreference } from "../features/settings/types/settings";
import { registerAppCommands, shell, useShell, type AgentSnapshot, type AppCommandName, type OrbStateName } from "./store";

type View = string;

export interface ShellBridgeInput {
  sakuraView: View;
  setSakuraView: (view: never) => void;
  theme: ThemePreference;
  setTheme: (theme: ThemePreference) => void;
  agent: AgentSnapshot;
  commands: Partial<Record<AppCommandName, () => void>>;
}

export function orbStateFrom(state: string): OrbStateName {
  return state === "listening" || state === "thinking" || state === "speaking" ? state : "idle";
}

/**
 * Connects the legacy conversation host (App) to the v2 shell: mode and theme
 * stay in sync both ways, agent state is published for the orb/inspector, and
 * palette commands are routed to the host. A no-op until a ShellLayout mounts.
 */
export function useShellBridge({ sakuraView, setSakuraView, theme, setTheme, agent, commands }: ShellBridgeInput): void {
  const hosted = useShell((s) => s.hosted);
  const mode = useShell((s) => s.mode);
  const shellTheme = useShell((s) => s.theme);
  const set = setSakuraView as (view: string) => void;
  const viewRef = useRef(sakuraView);
  viewRef.current = sakuraView;

  // shell mode → host view
  useEffect(() => {
    if (!hosted) return;
    if (mode === "companion") set("companion");
    else if (viewRef.current === "companion") set("work");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, hosted]);

  // host view → shell mode (legacy top bar can still flip views)
  const prevView = useRef(sakuraView);
  useEffect(() => {
    if (prevView.current === sakuraView) return;
    prevView.current = sakuraView;
    if (!hosted) return;
    if (sakuraView === "companion") shell.setMode("companion");
    else if (sakuraView === "work" || sakuraView === "showroom") shell.setMode("workspace");
  }, [sakuraView, hosted]);

  // theme: shell → settings, settings → shell
  useEffect(() => {
    if (hosted && shellTheme !== theme) setTheme(shellTheme);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shellTheme, hosted]);
  useEffect(() => {
    if (hosted) shell.adoptTheme(theme);
  }, [theme, hosted]);

  useEffect(() => {
    if (hosted) shell.publishAgent(agent);
  });

  useEffect(() => registerAppCommands(commands));
}
