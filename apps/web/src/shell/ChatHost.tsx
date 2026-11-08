import { useEffect } from "react";
import App from "../App";
import { Inspector } from "./Inspector";
import { shell, useShell } from "./store";

/**
 * Hosts the legacy conversation shell (App) once for both modes so chat state,
 * voice and the avatar survive Workspace ⇄ Companion switches. The companion
 * stage itself is rendered by App (it needs the live avatar/voice state).
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
    </div>
  );
}
