import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare, Mic, CheckSquare, FolderOpen, Brain, Wrench, Settings, Plus, ChevronRight, type LucideIcon,
} from "lucide-react";

export type NavSection = "chat" | "voice" | "tasks" | "files" | "memory" | "tools" | "settings";

interface NavRailProps {
  active: NavSection;
  onNavigate: (section: NavSection) => void;
  onNewChat: () => void;
  onSettings: () => void;
  expanded?: boolean;
}

const ITEMS: Array<{ id: NavSection; icon: LucideIcon; label: string; tooltip: string }> = [
  { id: "chat", icon: MessageSquare, label: "Conversations", tooltip: "Chat" },
  { id: "voice", icon: Mic, label: "Voice", tooltip: "Voice" },
  { id: "tasks", icon: CheckSquare, label: "Tasks", tooltip: "Tasks" },
  { id: "files", icon: FolderOpen, label: "Files", tooltip: "Files" },
  { id: "memory", icon: Brain, label: "Memory", tooltip: "Memory" },
  { id: "tools", icon: Wrench, label: "Tools", tooltip: "Tools" },
];

export function NavRail({ active, onNavigate, onNewChat, onSettings, expanded = false }: NavRailProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <nav className={`workspace-nav-rail${expanded ? " expanded" : ""}`} aria-label="HINAA Navigation">
      <div className="nav-rail-logo" aria-label="HINAA">
        <span className="nav-rail-logo-mark" aria-hidden="true">◇</span>
        {expanded && <span className="nav-rail-logo-text">HINAA</span>}
      </div>

      <motion.button
        className="nav-rail-item nav-rail-new"
        onClick={onNewChat}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.96 }}
        title="New conversation"
        aria-label="New conversation"
      >
        <Plus size={16} />
        {expanded && <span>New chat</span>}
      </motion.button>

      {ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = active === item.id;
        return (
          <div key={item.id} className="nav-rail-item-wrap">
            <motion.button
              className={`nav-rail-item${isActive ? " active" : ""}`}
              onClick={() => onNavigate(item.id)}
              aria-label={item.label}
              title={item.tooltip}
              onMouseEnter={() => setHovered(item.id)}
              onMouseLeave={() => setHovered(null)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
            >
              <Icon size={17} />
              {expanded && <span>{item.label}</span>}
            </motion.button>
            <AnimatePresence>
              {!expanded && hovered === item.id && (
                <motion.div
                  className="nav-rail-tooltip"
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -4 }}
                >
                  {item.tooltip}<ChevronRight size={13} aria-hidden="true" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}

      <div className="nav-rail-spacer" />
      <motion.button
        className={`nav-rail-item${active === "settings" ? " active" : ""}`}
        onClick={onSettings}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.96 }}
        title="Settings"
        aria-label="Settings"
      >
        <Settings size={17} />
        {expanded && <span>Settings</span>}
      </motion.button>
    </nav>
  );
}

export default NavRail;
