import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Kbd } from "../design-system/hud";
import { buildCommands, filterCommands } from "./commands";
import { shell, useShell } from "./store";

/** Global shortcuts: Ctrl/⌘+K opens the palette, Ctrl/⌘+. toggles the mode. */
export function useShellShortcuts(): void {
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        shell.togglePalette();
      } else if (mod && e.key === ".") {
        e.preventDefault();
        const next = shell.toggleMode();
        navigate(next === "companion" ? "/companion" : "/workspace");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);
}

export function CommandPalette() {
  const open = useShell((s) => s.paletteOpen);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const returnFocus = useRef<HTMLElement | null>(null);

  const results = useMemo(
    () => (open ? filterCommands(buildCommands(navigate, pathname), query) : []),
    [open, query, navigate, pathname],
  );

  useEffect(() => {
    if (open) {
      returnFocus.current = document.activeElement as HTMLElement | null;
      setQuery("");
      setActive(0);
      inputRef.current?.focus();
    } else {
      returnFocus.current?.focus?.();
    }
  }, [open]);

  if (!open) return null;

  const close = () => shell.setPalette(false);
  const runAt = (i: number) => {
    const cmd = results[i];
    if (!cmd) return;
    close();
    cmd.run();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, Math.max(results.length - 1, 0))); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); runAt(active); }
    else if (e.key === "Tab") { e.preventDefault(); inputRef.current?.focus(); }
  };

  return (
    <div className="shell-palette-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className="shell-palette" role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={onKeyDown}>
        <input
          ref={inputRef}
          className="shell-palette__input"
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-activedescendant={results[active] ? `${listId}-${results[active].id}` : undefined}
          aria-label="Search commands"
          placeholder="Type a command or search…"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setActive(0); }}
        />
        <ul id={listId} role="listbox" className="shell-palette__list" aria-label="Commands">
          {results.length === 0 && <li className="shell-palette__empty" role="presentation">No matching commands</li>}
          {results.map((cmd, i) => (
            <li
              key={cmd.id}
              id={`${listId}-${cmd.id}`}
              role="option"
              aria-selected={i === active}
              className="shell-palette__item"
              data-active={i === active}
              onMouseMove={() => setActive(i)}
              onClick={() => runAt(i)}
            >
              <span className="shell-palette__group">{cmd.group}</span>
              <span className="shell-palette__label">{cmd.label}</span>
              {cmd.shortcut && <Kbd>{cmd.shortcut}</Kbd>}
            </li>
          ))}
        </ul>
        <footer className="shell-palette__foot"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate <Kbd>Enter</Kbd> run <Kbd>Esc</Kbd> close</footer>
      </div>
    </div>
  );
}
