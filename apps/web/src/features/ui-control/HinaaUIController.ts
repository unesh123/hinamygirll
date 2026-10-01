/**
 * HINAA Autonomous UI Director & Interface Actuation Controller.
 *
 * Provides a bi-directional event bus allowing HINAA's intelligence engine,
 * voice turns, or desktop hotkeys to autonomously steer the workspace:
 * - Switching modes (Work, Showroom 3D, Operate, Vault)
 * - Navigating sections (Images, Projects, Library, Terminal, Settings, Memory)
 * - Controlling 3D avatar camera & presentation (3D, PIP, Hidden)
 * - Toggling slide-out drawers (Terminal Hands, Music, Settings, Memory)
 * - Controlling desktop window modes (Standard, Floating Companion, Compact Bar)
 * - Highlighting UI widgets during interactive walkthroughs
 */

export interface HinaaUIAction {
  action:
    | "navigate"
    | "switch_mode"
    | "switch_section"
    | "switch_operate_tab"
    | "set_avatar_mode"
    | "set_companion"
    | "toggle_drawer"
    | "set_theme"
    | "desktop_window_mode"
    | "highlight_element"
    | "trigger_voice";
  mode?: "talk" | "work" | "showroom" | "operate" | "vault";
  section?:
    | "talk"
    | "chat"
    | "voice"
    | "tasks"
    | "files"
    | "tools"
    | "images"
    | "library"
    | "projects"
    | "creations"
    | "memory"
    | "settings"
    | "terminal"
    | "vault"
    | "showroom"
    | "operate";
  tab?:
    | "tasks"
    | "capabilities"
    | "reports"
    | "orion"
    | "graph"
    | "policy"
    | "memory"
    | "verifier"
    | "rag"
    | "fleet"
    | "replay";
  avatar_mode?: "3d" | "pip" | "hidden";
  companion_id?: "hinaa" | "sakura" | "nova";
  drawer?: "terminal" | "settings" | "memory" | "music";
  open?: boolean;
  theme?: "dark" | "light";
  window_mode?: "standard" | "floating_companion" | "compact_bar" | "full_screen";
  selector?: string;
  label?: string;
  command?: string;
}

type UIActionListener = (action: HinaaUIAction) => void;

class HinaaUIEventBus {
  private listeners: Set<UIActionListener> = new Set();

  public subscribe(listener: UIActionListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public dispatch(action: HinaaUIAction): void {
    console.info("⚡ [HinaaUIController] Executing UI Action:", action);
    // Broadcast to internal listeners
    this.listeners.forEach((listener) => {
      try {
        listener(action);
      } catch (err) {
        console.error("UI Action listener error:", err);
      }
    });

    // Also dispatch to window DOM event for external or electron integration
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("hinaa:ui_action", { detail: action }));

      // If running inside HINAA Desktop App via Electron IPC:
      if ((window as any).hinaaDesktop?.onUIAction) {
        (window as any).hinaaDesktop.onUIAction(action);
      }
    }
  }

  public parseAndExecuteFromText(text: string): boolean {
    if (!text) return false;

    // Pattern: <hina_ui_action>{"action": "switch_mode", "mode": "showroom"}</hina_ui_action>
    const match = text.match(/<hina_ui_action>([\s\S]*?)<\/hina_ui_action>/i);
    if (match && match[1]) {
      try {
        const parsed = JSON.parse(match[1].trim());
        this.dispatch(parsed);
        return true;
      } catch (e) {
        console.warn("Failed to parse <hina_ui_action> tag:", e);
      }
    }
    return false;
  }

  public handleAssistantResponse(text: string): boolean {
    return this.parseAndExecuteFromText(text);
  }
}

export const hinaaUIController = new HinaaUIEventBus();
