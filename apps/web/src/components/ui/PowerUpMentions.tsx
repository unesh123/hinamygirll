/**
 * PowerUpMentions — power-up palette for both mention styles:
 *   @ → inserts a chat power-up token (model + tools understand it)
 *   / → slash command; entries with a `slash` alias insert the exact verb the
 *       backend deterministic router speaks (e.g. /research, /image).
 * Keyboard navigation: ↑↓ to move, Enter to select, Esc to close.
 */

import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, Image, Globe, Code, Music, Mail, Calendar,
  FileText, Brain, Sparkles, Wrench, Cpu, Download,
  ExternalLink, MessageSquare, Bot, Microscope, ScrollText, FolderSearch, FilePen, type LucideIcon,
} from "lucide-react";

export interface PowerUp {
  id: string;
  icon: LucideIcon;
  label: string;
  shortcut: string;
  /** Preferred insertion when the user opened the palette with "/" */
  slash?: string;
  description: string;
  color: string;
  group: string;
  action: string;
}

export const POWER_UPS: PowerUp[] = [
  { id: "@search", icon: Search, label: "Web Search", shortcut: "@search", description: "Search the web with sources", color: "#0891b2", group: "Knowledge", action: "search-web" },
  { id: "@image", icon: Image, label: "Find Images", shortcut: "@image", description: "Search for images online", color: "#7c3aed", group: "Knowledge", action: "image-search" },
  { id: "@generate", icon: Sparkles, label: "Generate Image", shortcut: "@generate", slash: "/generate", description: "Create AI artwork (Magnific FLUX)", color: "#d97706", group: "Create", action: "generate-image" },
  { id: "@research", icon: Microscope, label: "Deep Research", shortcut: "@research", slash: "/research", description: "Parallel multi-source cited dossier", color: "#0ea5e9", group: "Knowledge", action: "deep-research" },
  { id: "@report", icon: ScrollText, label: "Full Report", shortcut: "@report", slash: "/report", description: "Document-length structured answer", color: "#8b5cf6", group: "Create", action: "doc-mode" },
  { id: "@explore", icon: FolderSearch, label: "Explore Project", shortcut: "@explore", slash: "/explore", description: "Map the code workspace (tree, grep, symbols)", color: "#0891b2", group: "Automate", action: "explore-code" },
  { id: "@patch", icon: FilePen, label: "Patch a File", shortcut: "@patch", slash: "/patch", description: "Exact-match code edit with backup + diff", color: "#f97316", group: "Automate", action: "patch-code" },
  { id: "@browser", icon: Globe, label: "Open Browser", shortcut: "@browser", description: "Navigate to a website", color: "#059669", group: "Browse", action: "browser-navigate" },
  { id: "@read", icon: ExternalLink, label: "Read Page", shortcut: "@read", description: "Extract and summarize page content", color: "#14b8a6", group: "Browse", action: "browser-read" },
  { id: "@code", icon: Code, label: "Code Help", shortcut: "@code", description: "Write, explain, or debug code", color: "#dc2626", group: "Create", action: "write-code" },
  { id: "@music", icon: Music, label: "Play Music", shortcut: "@music", description: "Find and play on YouTube", color: "#ef4444", group: "Media", action: "play-music" },
  { id: "@email", icon: Mail, label: "Email", shortcut: "@email", description: "Check or send emails", color: "#3b82f6", group: "Connect", action: "check-email" },
  { id: "@calendar", icon: Calendar, label: "Calendar", shortcut: "@calendar", description: "View your schedule", color: "#8b5cf6", group: "Connect", action: "show-calendar" },
  { id: "@files", icon: FileText, label: "Files", shortcut: "@files", description: "Search and manage files", color: "#64748b", group: "Tools", action: "search-files" },
  { id: "@memory", icon: Brain, label: "Memory", shortcut: "@memory", description: "Save or recall memories", color: "#ec4899", group: "Tools", action: "remember-this" },
  { id: "@agent", icon: Bot, label: "Agent Mode", shortcut: "@agent", description: "Autonomous multi-step task", color: "#f97316", group: "Automate", action: "agent-mode" },
  { id: "@automate", icon: Wrench, label: "Automation", shortcut: "@automate", description: "Chain tool pipelines", color: "#f59e0b", group: "Automate", action: "automation" },
  { id: "@system", icon: Cpu, label: "System Tools", shortcut: "@system", description: "Open apps and system actions", color: "#6366f1", group: "Tools", action: "system-open" },
  { id: "@export", icon: Download, label: "Export", shortcut: "@export", description: "Download or save results", color: "#84cc16", group: "Tools", action: "export" },
];

interface PowerUpMentionsProps {
  visible: boolean;
  filter: string;
  /** Which sigil opened the palette — slash mode prefers /-aliases. */
  sigil?: "@" | "/";
  onSelect: (powerUp: PowerUp) => void;
  onClose: () => void;
}

export function PowerUpMentions({ visible, filter, onSelect, onClose, sigil = "@" }: PowerUpMentionsProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = filter.toLowerCase().replace(/^[@/]/, "");
    const matches = (p: PowerUp) =>
      !q
      || p.label.toLowerCase().includes(q)
      || p.shortcut.toLowerCase().includes(q)
      || (p.slash ?? "").toLowerCase().includes(q)
      || p.description.toLowerCase().includes(q)
      || p.group.toLowerCase().includes(q);
    const list = POWER_UPS.filter(matches);
    if (sigil === "/" && q) {
      // Slash users typed a verb — put exact slash-alias matches on top.
      list.sort((a, b) => {
        const at = a.slash?.toLowerCase().slice(1) === q ? 0 : a.slash?.toLowerCase().includes(q) ? 1 : 2;
        const bt = b.slash?.toLowerCase().slice(1) === q ? 0 : b.slash?.toLowerCase().includes(q) ? 1 : 2;
        return at - bt;
      });
    }
    return list;
  }, [filter, sigil]);

  // Nothing matches → hide the palette so Enter behaves as “send” again.
  useEffect(() => {
    if (visible && filtered.length === 0) onClose();
  }, [visible, filtered.length, onClose]);

  // Reset selection when filter changes
  useEffect(() => { setSelectedIndex(0); }, [filter]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        onSelect(filtered[selectedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    },
    [visible, filtered, selectedIndex, onSelect, onClose],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Scroll selected into view
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const selected = container.children[selectedIndex] as HTMLElement;
    if (selected) {
      selected.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [selectedIndex]);

  // Group power-ups
  const groups = useMemo(() => {
    const map = new Map<string, PowerUp[]>();
    for (const p of filtered) {
      const list = map.get(p.group) || [];
      list.push(p);
      map.set(p.group, list);
    }
    return Array.from(map.entries());
  }, [filtered]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.96 }}
          transition={{ duration: 0.18, ease: [0.22, 0.61, 0.36, 1] }}
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: 0,
            background: "rgba(255,255,255,0.92)",
            backdropFilter: "blur(28px)",
            WebkitBackdropFilter: "blur(28px)",
            borderRadius: 18,
            border: "1px solid rgba(255,255,255,0.85)",
            boxShadow: "0 12px 60px rgba(0,0,0,0.1), 0 2px 12px rgba(0,0,0,0.04)",
            padding: "10px 8px",
            zIndex: 200,
            width: 360,
            maxHeight: 420,
            overflow: "hidden",
          }}
        >
          <div
            ref={containerRef}
            style={{
              maxHeight: 380,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {groups.map(([group, items]) => (
              <div key={group}>
                <div
                  style={{
                    fontSize: "0.65rem",
                    fontWeight: 700,
                    color: "#94a3b8",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    padding: "4px 8px",
                  }}
                >
                  {group}
                </div>
                {items.map((powerUp) => {
                  const idx = filtered.indexOf(powerUp);
                  const isSelected = idx === selectedIndex;
                  const Icon = powerUp.icon;

                  return (
                    <motion.button
                      key={powerUp.id}
                      type="button"
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.02 }}
                      onClick={() => onSelect(powerUp)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "8px 10px",
                        border: "none",
                        borderRadius: 10,
                        background: isSelected ? "rgba(167,243,208,0.25)" : "transparent",
                        cursor: "pointer",
                        width: "100%",
                        textAlign: "left",
                        fontFamily: "inherit",
                        transition: "background 0.12s ease",
                      }}
                    >
                      <span
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 9,
                          background: `${powerUp.color}16`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          border: isSelected ? `1px solid ${powerUp.color}40` : "1px solid transparent",
                        }}
                      >
                        <Icon size={15} color={powerUp.color} />
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#1a1f2e" }}>
                          {powerUp.label}
                        </div>
                        <div style={{ fontSize: "0.67rem", color: "#94a3b8", marginTop: 1 }}>
                          {powerUp.description}
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: "0.6rem",
                          fontWeight: 700,
                          color: isSelected ? powerUp.color : "#cbd5e1",
                          background: isSelected ? `${powerUp.color}12` : "rgba(0,0,0,0.04)",
                          padding: "2px 8px",
                          borderRadius: 6,
                          fontFamily: "monospace",
                        }}
                      >
                        {powerUp.shortcut}
                      </span>
                    </motion.button>
                  );
                })}
              </div>
            ))}
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 16,
              padding: "6px 0 2px",
              borderTop: "1px solid rgba(0,0,0,0.05)",
              marginTop: 4,
            }}
          >
            <span style={{ fontSize: "0.62rem", color: "#cbd5e1" }}>↑↓ navigate</span>
            <span style={{ fontSize: "0.62rem", color: "#cbd5e1" }}>↵ select</span>
            <span style={{ fontSize: "0.62rem", color: "#cbd5e1" }}>esc close</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default PowerUpMentions;
