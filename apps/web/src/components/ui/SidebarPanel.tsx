import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight, Brain, CheckSquare, FolderOpen, Image, Mic, Plus, Search, Settings, Sparkles, Wand2, X,
} from "lucide-react";
import type { NavSection } from "./NavRail";

interface SidebarPanelProps {
  section: NavSection | null;
  onClose: () => void;
  onNewChat?: () => void;
  onStartVoice?: () => void;
  onOpenMemory?: () => void;
  onOpenImageStudio?: () => void;
  onOpenHumanizer?: () => void;
  onOpenProjects?: () => void;
  onOpenSettings?: () => void;
  onQuickPrompt?: (prompt: string) => void;
}

type Shortcut = {
  label: string;
  detail: string;
  icon: React.ReactNode;
  action?: () => void;
};

function panelTitle(section: NavSection): string {
  return ({ chat: "Conversation", voice: "Voice", tasks: "Projects", files: "Projects", memory: "Memory", tools: "Local tools", settings: "Settings" } as const)[section];
}

function shortcutsFor(section: NavSection, props: SidebarPanelProps): { eyebrow: string; heading: string; copy: string; items: Shortcut[] } {
  const openProjects = props.onOpenProjects;
  switch (section) {
    case "chat":
      return {
        eyebrow: "PRIVATE CONVERSATION",
        heading: "Start with a clear outcome",
        copy: "This local session stays ready while HINAA works. Start a fresh conversation whenever you want a clean context.",
        items: [
          { label: "New conversation", detail: "Start a clean private chat", icon: <Plus size={16} />, action: props.onNewChat },
          { label: "Plan my work", detail: "Create a practical task plan", icon: <CheckSquare size={16} />, action: () => props.onQuickPrompt?.("Turn my goal into a clear task plan with milestones, dependencies, and approval points: ") },
        ],
      };
    case "voice":
      return {
        eyebrow: "VOICE PRESENCE",
        heading: "Talk naturally, with a clear fallback",
        copy: "HINAA uses the configured voice route when available and transparently falls back to browser speech when it is not.",
        items: [
          { label: "Start voice conversation", detail: "Use your microphone", icon: <Mic size={16} />, action: props.onStartVoice },
          { label: "Voice and language settings", detail: "Choose the active Hindi / English route", icon: <Settings size={16} />, action: props.onOpenSettings },
        ],
      };
    case "memory":
      return {
        eyebrow: "CONSENT-BASED MEMORY",
        heading: "Review what HINAA may retain",
        copy: "Memory remains local and should contain only facts you explicitly choose to save or manage.",
        items: [
          { label: "Open Memory", detail: "Review and manage saved facts", icon: <Brain size={16} />, action: props.onOpenMemory },
          { label: "Remember a preference", detail: "Draft a consent-based memory request", icon: <Plus size={16} />, action: () => props.onQuickPrompt?.("Remember this preference only after showing me what will be saved: ") },
        ],
      };
    case "tools":
      return {
        eyebrow: "LOCAL WORKBENCH",
        heading: "Choose an action, then stay in control",
        copy: "Availability depends on your local services and configured providers. HINAA shows a safe state rather than pretending an unavailable tool is ready.",
        items: [
          { label: "Research with sources", detail: "Ask for attributable findings", icon: <Search size={16} />, action: () => props.onQuickPrompt?.("Research this with clear sources and practical next steps: ") },
          { label: "Create an image", detail: "Open the local Image Studio", icon: <Image size={16} />, action: props.onOpenImageStudio },
          { label: "Humanize a draft", detail: "Polish text locally; no provider required", icon: <Wand2 size={16} />, action: props.onOpenHumanizer },
          { label: "Check local diagnostics", detail: "Review configured services", icon: <Settings size={16} />, action: props.onOpenSettings },
        ],
      };
    case "tasks":
    case "files":
      return {
        eyebrow: "LOCAL PROJECTS",
        heading: "Keep work, sources, and artifacts together",
        copy: "Projects are stored in HINAA’s local workspace. Open one to create a task tree, save sources, or export artifacts.",
        items: [
          { label: "Open local projects", detail: "Manage task trees and artifacts", icon: <FolderOpen size={16} />, action: openProjects },
          { label: "Create a work plan", detail: "Turn a goal into a project", icon: <CheckSquare size={16} />, action: () => props.onQuickPrompt?.("Help me create a local project plan for: ") },
        ],
      };
    case "settings":
      return {
        eyebrow: "LOCAL SETTINGS",
        heading: "Control how HINAA works for you",
        copy: "Review appearance, language, provider, and safe diagnostics in one place. Credentials remain local and are never displayed here.",
        items: [
          { label: "Open settings", detail: "Language, appearance, providers, and diagnostics", icon: <Settings size={16} />, action: props.onOpenSettings },
        ],
      };
  }
}

export function SidebarPanel(props: SidebarPanelProps) {
  const { section, onClose } = props;
  if (!section) return null;
  const content = shortcutsFor(section, props);

  return (
    <AnimatePresence>
      <motion.aside
        key="sidebar-panel"
        aria-label={`${panelTitle(section)} shortcuts`}
        initial={{ x: -320, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: -320, opacity: 0 }}
        transition={{ duration: 0.22, ease: [0.23, 1, 0.32, 1] }}
        className="hinaa-shortcuts-panel"
      >
        <header className="hinaa-shortcuts-panel__header">
          <span>{panelTitle(section)}</span>
          <button type="button" onClick={onClose} aria-label="Close shortcuts panel"><X size={15} /></button>
        </header>
        <div className="hinaa-shortcuts-panel__body">
          <p className="hinaa-shortcuts-panel__eyebrow">{content.eyebrow}</p>
          <h2>{content.heading}</h2>
          <p className="hinaa-shortcuts-panel__copy">{content.copy}</p>
          <div className="hinaa-shortcuts-panel__list">
            {content.items.map((item) => (
              <button key={item.label} type="button" className="hinaa-shortcut" onClick={item.action} disabled={!item.action}>
                <span className="hinaa-shortcut__icon" aria-hidden="true">{item.icon}</span>
                <span className="hinaa-shortcut__text"><strong>{item.label}</strong><small>{item.detail}</small></span>
                <ArrowRight size={15} aria-hidden="true" />
              </button>
            ))}
          </div>
          <div className="hinaa-shortcuts-panel__note"><Sparkles size={14} aria-hidden="true" /> <span>HINAA keeps external actions explicit and local-service status truthful.</span></div>
        </div>
      </motion.aside>
    </AnimatePresence>
  );
}

export default SidebarPanel;
