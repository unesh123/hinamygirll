import { lazy, Suspense, useEffect } from "react";
import App from "../App";
const CompanionHud = lazy(() => import("./CompanionHud"));
import { Inspector } from "./Inspector";
import { shell, useShell } from "./store";

/**
 * Hosts the legacy conversation shell (App) once for both modes so chat state,
 * voice and the avatar survive Workspace ⇄ Companion switches.
 */
export function ChatHost() {
  const mode = useShell((s) => s.mode);
  useEffect(() => {
    shell.setHosted(true);
    return () => shell.setHosted(false);
  }, []);
  return (
    <div className="shell-host" data-mode={mode}>
      <div className="shell-host__app"><App /></div>
      {mode === "workspace" && <Inspector />}
      {mode === "companion" && <Suspense fallback={null}><CompanionHud /></Suspense>}
    </div>
  );
}
