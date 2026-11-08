import { MODE_PATHS, resolveIsDark, runAppCommand, shell, getShellState, type InspectorTab, type ShellMode } from "./store";

export interface ShellCommand {
  id: string;
  label: string;
  group: "Navigate" | "Mode" | "Actions" | "Panels";
  keywords?: string;
  shortcut?: string;
  run: () => void;
}

export const PAGE_ROUTES = [
  { path: "/goals", label: "Goals", keywords: "plan milestones objectives" },
  { path: "/autopilot", label: "Autopilot", keywords: "schedules jobs automation" },
  { path: "/security", label: "Security", keywords: "permissions audit approvals posture" },
  { path: "/integrations", label: "Integrations", keywords: "connectors skills mcp tools" },
  { path: "/memory", label: "Memory", keywords: "real memory about preferences projects" },
  { path: "/productivity", label: "Productivity", keywords: "content calendar posts sales projects tasks revenue" },
  { path: "/news", label: "News", keywords: "digest watchlist rss headlines youtube publish social" },
] as const;

/** Whether the legacy conversation host is on screen (workspace/companion routes). */
function onHostRoute(pathname: string): boolean {
  return pathname === MODE_PATHS.workspace || pathname === MODE_PATHS.companion;
}

export function buildCommands(navigate: (path: string) => void, pathname: string): ShellCommand[] {
  const goMode = (mode: ShellMode) => () => {
    shell.setMode(mode);
    navigate(MODE_PATHS[mode]);
  };
  const hostAction = (name: Parameters<typeof runAppCommand>[0], mode: ShellMode = "workspace") => () => {
    if (!onHostRoute(pathname)) {
      shell.setMode(mode);
      navigate(MODE_PATHS[mode]);
    }
    runAppCommand(name);
  };
  const panel = (tab: InspectorTab) => () => {
    if (!onHostRoute(pathname)) {
      shell.setMode("workspace");
      navigate(MODE_PATHS.workspace);
    }
    shell.setInspector(true, tab);
  };

  return [
    { id: "mode-workspace", group: "Mode", label: "Switch to Workspace mode", keywords: "pro agent chat", run: goMode("workspace") },
    { id: "mode-companion", group: "Mode", label: "Switch to Companion mode", keywords: "avatar hina talk", shortcut: "Ctrl+.", run: goMode("companion") },
    ...PAGE_ROUTES.map((r): ShellCommand => ({
      id: `go-${r.path.slice(1)}`, group: "Navigate", label: `Go to ${r.label}`, keywords: r.keywords, run: () => navigate(r.path),
    })),
    { id: "go-chat", group: "Navigate", label: "Go to Chat", keywords: "conversation workspace", run: goMode("workspace") },
    { id: "new-chat", group: "Actions", label: "New chat", keywords: "conversation reset", run: hostAction("new-chat") },
    { id: "start-voice", group: "Actions", label: "Start voice", keywords: "talk microphone listen", run: hostAction("start-voice", "companion") },
    { id: "stop-voice", group: "Actions", label: "Stop voice", keywords: "mute microphone", run: hostAction("stop-voice") },
    { id: "toggle-vision", group: "Actions", label: "Toggle camera awareness", keywords: "webcam vision see camera", run: hostAction("toggle-vision", "companion") },
    { id: "open-settings", group: "Actions", label: "Open settings", keywords: "preferences", run: hostAction("open-settings") },
    { id: "open-terminal", group: "Actions", label: "Open terminal", keywords: "shell hands", run: hostAction("open-terminal") },
    { id: "toggle-history", group: "Actions", label: "Toggle conversation history", keywords: "search past chats", run: hostAction("toggle-history") },
    { id: "open-projects", group: "Actions", label: "Open local projects", keywords: "files workspace", run: hostAction("open-projects") },
    { id: "open-image-studio", group: "Actions", label: "Open image studio", keywords: "generate pictures", run: hostAction("open-image-studio") },
    { id: "open-showroom", group: "Actions", label: "Open Showroom", keywords: "runway catwalk 3d outfits", run: hostAction("open-showroom") },
    { id: "toggle-theme", group: "Actions", label: resolveIsDark(getShellState().theme) ? "Switch to light theme" : "Switch to dark theme", keywords: "appearance dark light", run: () => shell.toggleTheme() },
    { id: "panel-plan", group: "Panels", label: "Open Plan / Run timeline", keywords: "steps inspector", run: panel("plan") },
    { id: "panel-tools", group: "Panels", label: "Open Tools panel", keywords: "inspector", run: panel("tools") },
    { id: "panel-memory", group: "Panels", label: "Open Memory panel", keywords: "inspector remember", run: panel("memory") },
    { id: "panel-integrations", group: "Panels", label: "Open Integrations panel", keywords: "inspector connectors", run: panel("integrations") },
  ];
}

export function filterCommands(commands: ShellCommand[], query: string): ShellCommand[] {
  const q = query.trim().toLowerCase();
  if (!q) return commands;
  const terms = q.split(/\s+/);
  return commands.filter((c) => {
    const hay = `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase();
    return terms.every((t) => hay.includes(t));
  });
}
