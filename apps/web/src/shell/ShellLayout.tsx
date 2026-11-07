import { Suspense, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import "../design-system/hud";
import "./shell.css";
import { CommandPalette, useShellShortcuts } from "./CommandPalette";
import { RouteErrorBoundary } from "./RouteErrorBoundary";
import { ShellBar } from "./ShellBar";
import { MODE_PATHS, applyThemeToDom, getShellState, shell, useShell, type ShellMode } from "./store";

export function modeForPath(pathname: string): ShellMode | null {
  if (pathname === MODE_PATHS.workspace) return "workspace";
  if (pathname === MODE_PATHS.companion) return "companion";
  return null;
}

/** Frame for every route: top bar, palette, theme, and the routed page. */
export function ShellLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  useShellShortcuts();

  useEffect(() => { applyThemeToDom(getShellState().theme); }, []);

  // Deep links: adopt the URL's mode before first paint so nothing sees a stale one.
  useState(() => {
    const fromPath = modeForPath(pathname);
    if (fromPath) shell.setMode(fromPath);
  });
  const mode = useShell((s) => s.mode);
  // Back/forward navigation changes the URL → mode.
  useEffect(() => {
    const fromPath = modeForPath(pathname);
    if (fromPath) shell.setMode(fromPath);
  }, [pathname]);

  // mode → URL (set by the legacy host or by the store)
  const lastMode = useRef(mode);
  useEffect(() => {
    if (lastMode.current === mode) return;
    lastMode.current = mode;
    if (modeForPath(pathname)) navigate(MODE_PATHS[mode], { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  return (
    <div className="shell-root" data-shell-mode={mode}>
      <a className="shell-skip" href="#shell-main">Skip to content</a>
      <ShellBar />
      <div id="shell-main" className="shell-stage" tabIndex={-1}>
        <RouteErrorBoundary resetKey={pathname}>
        <Suspense fallback={<p className="shell-state" role="status">Loading…</p>}>
          <Outlet />
        </Suspense>
        </RouteErrorBoundary>
      </div>
      <CommandPalette />
    </div>
  );
}
