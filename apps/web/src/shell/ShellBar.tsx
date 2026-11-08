import { NavLink, useNavigate } from "react-router-dom";
import { Moon, PanelRight, Search, Sparkles, Sun, Briefcase } from "lucide-react";
import { Button, Kbd } from "../design-system/hud";
import { PAGE_ROUTES } from "./commands";
import { MODE_PATHS, resolveIsDark, shell, useShell, type ShellMode } from "./store";

const MODES: { id: ShellMode; label: string; icon: typeof Briefcase }[] = [
  { id: "workspace", label: "Workspace", icon: Briefcase },
  { id: "companion", label: "Companion", icon: Sparkles },
];

export function ModeSwitch() {
  const mode = useShell((s) => s.mode);
  const navigate = useNavigate();
  return (
    <div className="shell-mode" role="radiogroup" aria-label="Interface mode">
      {MODES.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={mode === id}
          aria-label={label}
          className="shell-mode__opt ds-focusable"
          data-active={mode === id}
          onClick={() => { shell.setMode(id); navigate(MODE_PATHS[id]); }}
        >
          <Icon size={14} aria-hidden="true" />
          <span className="shell-mode__label">{label}</span>
        </button>
      ))}
    </div>
  );
}

export function ShellBar() {
  const theme = useShell((s) => s.theme);
  const inspectorOpen = useShell((s) => s.inspectorOpen);
  const mode = useShell((s) => s.mode);
  const dark = resolveIsDark(theme);
  return (
    <header className="shell-bar">
      <NavLink to={MODE_PATHS[mode]} className="shell-bar__brand ds-focusable" aria-label="Hina home">Hina</NavLink>
      <ModeSwitch />
      <nav className="shell-bar__nav" aria-label="Pages">
        {PAGE_ROUTES.map((r) => (
          <NavLink key={r.path} to={r.path} className={({ isActive }) => `shell-bar__link ds-focusable${isActive ? " is-active" : ""}`}>
            {r.label}
          </NavLink>
        ))}
      </nav>
      <div className="shell-bar__tools">
        <Button variant="secondary" onClick={() => shell.setPalette(true)} aria-label="Open command palette" aria-keyshortcuts="Control+K Meta+K">
          <Search size={14} aria-hidden="true" /> <span className="shell-bar__hide-sm">Search</span> <Kbd className="shell-bar__hide-sm">Ctrl K</Kbd>
        </Button>
        {mode === "workspace" && (
          <Button variant="ghost" icon aria-label="Toggle inspector" aria-pressed={inspectorOpen} onClick={() => shell.setInspector(!inspectorOpen)}>
            <PanelRight size={16} aria-hidden="true" />
          </Button>
        )}
        <Button variant="ghost" icon aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => shell.toggleTheme()}>
          {dark ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
        </Button>
      </div>
    </header>
  );
}
