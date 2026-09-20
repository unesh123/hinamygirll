/**
 * PowerUpMentions — @ context picker and / command palette for HINAA.
 * 
 * @ opens the context picker (projects, files, memories, artifacts, etc.)
 * / opens the command palette (search, research, generate, analyze, etc.)
 * 
 * Keyboard navigation: ↑↓ to move, Enter to select, Esc to close, Tab to switch tabs.
 */

import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, Image, Sparkles, Globe, ExternalLink, Code, Music,
  Mail, Calendar, FileText, Brain, Bot, Wrench, Cpu, MessageSquare,
  LayoutDashboard, FileOutput, Presentation, Zap, BookOpen, Mic,
  Settings, Monitor, GitBranch, Wand2, Download, Microscope, ScrollText, type LucideIcon,
} from "lucide-react";

export type TriggerType = "@" | "/";

/** @deprecated Use ContextItem | CommandItem instead */
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

export interface ContextItem {
  id: string;
  kind: string;
  label: string;
  description: string;
  icon: LucideIcon;
  color: string;
  sourceId: string;
  access: "read" | "use" | "execute";
}

export interface CommandItem {
  name: string;
  aliases: string[];
  label: string;
  description: string;
  descriptionShort: string;
  icon: LucideIcon;
  color: string;
  group: string;
  inputSchema: Record<string, any>;
  capability: string;
  riskLevel: "read" | "low-mutation" | "external-mutation" | "high-impact";
  approvalPolicy: "automatic" | "session-consent" | "always-confirm" | "prohibited";
  availability: "unconfigured" | "configured" | "available" | "degraded" | "unavailable" | "verifying";
  executionLocation: "browser" | "api" | "worker" | "desktop_bridge" | "external_provider";
  examples: string[];
}

const CONTEXT_ICONS: Record<string, LucideIcon> = {
  project: GitBranch,
  file: FileText,
  folder: FileText,
  conversation: MessageSquare,
  memory: Brain,
  task: LayoutDashboard,
  artifact: FileOutput,
  tool: Wrench,
  browser_page: Globe,
  selected_text: BookOpen,
};

const CONTEXT_COLORS: Record<string, string> = {
  project: "#7c3aed",
  file: "#0891b2",
  folder: "#059669",
  conversation: "#14b8a6",
  memory: "#ec4899",
  task: "#f97316",
  artifact: "#d97706",
  tool: "#64748b",
  browser_page: "#dc2626",
  selected_text: "#10b981",
};

const COMMAND_ICONS: Record<string, LucideIcon> = {
  search: Search,
  research: Brain,
  answer: Sparkles,
  extract: ExternalLink,
  image_search: Image,
  image_generate: Sparkles,
  image: Sparkles,
  draw: Sparkles,
  generate: Sparkles,
  img: Sparkles,
  pic: Sparkles,
  web: Search,
  google: Search,
  humanize: Wand2,
  document: FileText,
  pdf: FileOutput,
  presentation: Presentation,
  analyze: Zap,
  summarize: BookOpen,
  plan: LayoutDashboard,
  play: Music,
  memory: Brain,
  files: FileText,
  model: Cpu,
  voice: Mic,
  avatar: Bot,
  settings: Settings,
  automate: Wrench,
};

const COMMAND_COLORS: Record<string, string> = {
  search: "#0891b2",
  research: "#7c3aed",
  answer: "#10b981",
  extract: "#14b8a6",
  image_search: "#7c3aed",
  image_generate: "#F36F9C",
  image: "#F36F9C",
  draw: "#F36F9C",
  generate: "#F36F9C",
  img: "#F36F9C",
  pic: "#F36F9C",
  web: "#0891b2",
  google: "#0891b2",
  humanize: "#5B9DCF",
  document: "#059669",
  pdf: "#dc2626",
  presentation: "#f97316",
  analyze: "#ec4899",
  summarize: "#0891b2",
  plan: "#7c3aed",
  play: "#ef4444",
  memory: "#ec4899",
  files: "#64748b",
  model: "#dc2626",
  voice: "#10b981",
  avatar: "#f97316",
  settings: "#64748b",
  automate: "#f59e0b",
};

const COMMAND_GROUPS: Record<string, string> = {
  search: "Search & Research",
  research: "Search & Research",
  answer: "Search & Research",
  extract: "Search & Research",
  web: "Search & Research",
  google: "Search & Research",
  image_search: "Create",
  image_generate: "Create",
  image: "Create",
  draw: "Create",
  generate: "Create",
  img: "Create",
  pic: "Create",
  document: "Create",
  pdf: "Create",
  presentation: "Create",
  humanize: "Writing",
  analyze: "Analyze",
  summarize: "Analyze",
  plan: "Plan",
  play: "Media",
  memory: "Tools",
  files: "Tools",
  model: "Tools",
  voice: "Tools",
  avatar: "Tools",
  settings: "Tools",
  automate: "Automate",
};

const AVAILABILITY_LABELS: Record<string, string> = {
  unconfigured: "Not configured",
  configured: "Configured",
  available: "Ready",
  degraded: "Limited",
  unavailable: "Unavailable",
  verifying: "Checking…",
};

const AVAILABILITY_COLORS: Record<string, string> = {
  unconfigured: "#64748b",
  configured: "#f59e0b",
  available: "#10b981",
  degraded: "#f97316",
  unavailable: "#ef4444",
  verifying: "#0891b2",
};

export const POWER_UPS: PowerUp[] = [
  { id: "@search", icon: Search, label: "Web Search", shortcut: "@search", description: "Search the web with sources", color: "#0891b2", group: "Knowledge", action: "search-web" },
  { id: "@image", icon: Image, label: "Find Images", shortcut: "@image", description: "Search for images online", color: "#7c3aed", group: "Knowledge", action: "image-search" },
  { id: "@generate", icon: Sparkles, label: "Generate Image", shortcut: "@generate", slash: "/generate", description: "Create AI artwork (Magnific FLUX)", color: "#d97706", group: "Create", action: "generate-image" },
  { id: "@research", icon: Microscope, label: "Deep Research", shortcut: "@research", slash: "/research", description: "Parallel multi-source cited dossier", color: "#0ea5e9", group: "Knowledge", action: "deep-research" },
  { id: "@report", icon: ScrollText, label: "Full Report", shortcut: "@report", slash: "/report", description: "Document-length structured answer", color: "#8b5cf6", group: "Create", action: "doc-mode" },
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

export interface PowerUpMentionsProps {
  visible: boolean;
  filter: string;
  onSelectContext?: (context: ContextItem) => void;
  onSelectCommand?: (command: CommandItem, args?: string) => void;
  /** Which sigil opened the palette — slash mode prefers /-aliases. */
  sigil?: "@" | "/";
  onSelect?: (powerUp: PowerUp) => void;
  onClose: () => void;
  trigger?: TriggerType;
  contexts?: ContextItem[];
  commands?: CommandItem[];
}

export function PowerUpMentions({
  visible,
  filter,
  onSelectContext,
  onSelectCommand,
  onSelect,
  onClose,
  sigil,
  trigger = sigil ?? "@",
  contexts = [],
  commands = [],
}: PowerUpMentionsProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"contexts" | "commands">(trigger === "@" ? "contexts" : "commands");
  const containerRef = useRef<HTMLDivElement>(null);

  const isLegacyMode = Boolean(onSelect);

  // Follow trigger changes: the palette stays mounted, so "@" must always
  // show contexts and "/" must always show commands.
  useEffect(() => {
    setActiveTab(trigger === "@" ? "contexts" : "commands");
  }, [trigger]);

  const filteredLegacy = useMemo(() => {
    const q = filter.toLowerCase().replace(/^[@/]/, "");
    const matches = (p: PowerUp) =>
      !q
      || p.label.toLowerCase().includes(q)
      || p.shortcut.toLowerCase().includes(q)
      || (p.slash ?? "").toLowerCase().includes(q)
      || p.description.toLowerCase().includes(q)
      || p.group.toLowerCase().includes(q);
    const list = POWER_UPS.filter(matches);
    const currentSigil = sigil || (trigger === "/" ? "/" : "@");
    if (currentSigil === "/" && q) {
      // Slash users typed a verb — put exact slash-alias matches on top.
      list.sort((a, b) => {
        const at = a.slash?.toLowerCase().slice(1) === q ? 0 : a.slash?.toLowerCase().includes(q) ? 1 : 2;
        const bt = b.slash?.toLowerCase().slice(1) === q ? 0 : b.slash?.toLowerCase().includes(q) ? 1 : 2;
        return at - bt;
      });
    }
    return list;
  }, [filter, sigil, trigger]);

  // Nothing matches in legacy mode → hide the palette so Enter behaves as "send" again.
  useEffect(() => {
    if (isLegacyMode && visible && filteredLegacy.length === 0) onClose();
  }, [isLegacyMode, visible, filteredLegacy.length, onClose]);

  const filteredContexts = useMemo(() => {
    const q = filter.toLowerCase();
    if (!q) return contexts;
    return contexts.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.kind.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q),
    );
  }, [filter, contexts]);

  const filteredCommands = useMemo(() => {
    const q = filter.toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) =>
        (c.label?.toLowerCase() || "").includes(q) ||
        (c.name?.toLowerCase() || "").includes(q) ||
        (c.aliases || []).some((a) => a?.toLowerCase().includes(q)) ||
        (c.description?.toLowerCase() || "").includes(q) ||
        (c.descriptionShort?.toLowerCase() || "").includes(q) ||
        ((c.group || COMMAND_GROUPS[c.name])?.toLowerCase() || "").includes(q),
    );
  }, [filter, commands]);

  const activeItems = isLegacyMode ? (filteredLegacy as any as (ContextItem | CommandItem)[]) : (activeTab === "contexts" ? filteredContexts : filteredCommands);

  // Reset selection when filter or tab changes
  useEffect(() => { setSelectedIndex(0); }, [filter, activeTab]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible) return;

      // Consume the key so it never reaches the composer's React handler.
      const own = () => {
        e.preventDefault();
        e.stopPropagation();
      };

      // Tab to switch between contexts and commands
      if (e.key === "Tab") {
        own();
        setActiveTab((prev) => (prev === "contexts" ? "commands" : "contexts"));
        return;
      }

      if (e.key === "ArrowDown") {
        own();
        setSelectedIndex((i) => Math.min(i + 1, activeItems.length - 1));
      } else if (e.key === "ArrowUp") {
        own();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        if (isLegacyMode) {
          if (!filteredLegacy[selectedIndex]) return;
          own();
          onSelect?.(filteredLegacy[selectedIndex]);
          return;
        }
        if (!activeItems[selectedIndex]) return;
        own();
        const item = activeItems[selectedIndex];
        if (activeTab === "contexts") {
          onSelectContext?.(item as ContextItem);
        } else {
          onSelectCommand?.(item as CommandItem);
        }
      } else if (e.key === "Escape") {
        own();
        onClose();
      }
    },
    [visible, activeItems, selectedIndex, activeTab, isLegacyMode, filteredLegacy, onSelect, onSelectContext, onSelectCommand, onClose],
  );

  useEffect(() => {
    // Capture phase, deliberately. React attaches its synthetic handler to the
    // root container, so a bubble-phase listener on `window` only sees the key
    // after the textarea has already handled Enter and submitted the chat.
    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, [handleKeyDown]);

  // Scroll selected into view
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const selected = container.querySelector("[data-selected='true']") as HTMLElement | null;
    if (selected && typeof selected.scrollIntoView === "function") {
      selected.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [selectedIndex]);

  // Group items
  const groups = useMemo(() => {
    if (isLegacyMode) {
      const map = new Map<string, (ContextItem | CommandItem)[]>();
      for (const p of filteredLegacy) {
        const list = map.get(p.group) || [];
        list.push(p as any);
        map.set(p.group, list);
      }
      return Array.from(map.entries());
    }
    const map = new Map<string, (ContextItem | CommandItem)[]>();
    for (const item of activeItems) {
      const group = "group" in item && item.group ? item.group : ("name" in item ? (COMMAND_GROUPS[item.name] || "Commands") : (item.kind || "Context"));
      const list = map.get(group) || [];
      list.push(item);
      map.set(group, list);
    }
    return Array.from(map.entries());
  }, [isLegacyMode, filteredLegacy, activeItems]);

  if (!visible) return null;

  const Icon = activeTab === "contexts" ? Search : Bot;

  return (
    <AnimatePresence>
      <motion.div
        className="hinaa-command-popover"
        role="dialog"
        aria-label={trigger === "/" ? "HINAA slash commands" : "HINAA context picker"}
        initial={{ opacity: 0, y: 8, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.96 }}
        transition={{ duration: 0.18, ease: [0.22, 0.61, 0.36, 1] }}
        style={{
          position: "absolute",
          bottom: "calc(100% + 8px)",
          left: 0,
          background: "var(--surface-overlay)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-default)",
          boxShadow: "var(--shadow-overlay)",
          padding: "10px 8px",
          zIndex: 200,
          width: "min(400px, calc(100vw - 24px))",
          maxHeight: 480,
          overflow: "hidden",
        }}
      >
        {/* Tab bar */}
        {!isLegacyMode && (
        <div style={{ display: "flex", gap: 4, marginBottom: 8, padding: "0 4px 8px", borderBottom: "1px solid var(--border-subtle)" }}>
          <button
            type="button"
            onClick={() => setActiveTab("contexts")}
            style={{
              flex: 1,
              padding: "6px 12px",
              borderRadius: 8,
              border: "none",
              background: activeTab === "contexts" ? "var(--accent-subtle)" : "transparent",
              color: activeTab === "contexts" ? "var(--text-accent)" : "var(--text-secondary)",
              fontSize: "0.7rem",
              fontWeight: 600,
              fontFamily: "inherit",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
            }}
          >
            <MessageSquare size={12} />
            <span>@ Contexts ({contexts.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("commands")}
            style={{
              flex: 1,
              padding: "6px 12px",
              borderRadius: 8,
              border: "none",
              background: activeTab === "commands" ? "var(--accent-subtle)" : "transparent",
              color: activeTab === "commands" ? "var(--text-accent)" : "var(--text-secondary)",
              fontSize: "0.7rem",
              fontWeight: 600,
              fontFamily: "inherit",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
            }}
          >
            <Bot size={12} />
            <span>/ Commands ({commands.length})</span>
          </button>
        </div>
        )}

        <div
          ref={containerRef}
          className="hinaa-command-popover__list"
          style={{
            maxHeight: 420,
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
                  color: "var(--text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  padding: "4px 8px",
                }}
              >
                {group}
              </div>
              {items.map((item) => {
                const idx = activeItems.findIndex((i) => i === item);
                const isSelected = idx === selectedIndex;
                const isContext = activeTab === "contexts";
                
                // Type guard for ContextItem
                const isContextItem = (item: ContextItem | CommandItem): item is ContextItem => 
                  "kind" in item && "sourceId" in item;
                
                if (isLegacyMode) {
                  const powerUp = item as any as PowerUp;
                  const Icon = powerUp.icon;
                  return (
                    <motion.button
                      key={powerUp.id}
                      type="button"
                      data-selected={isSelected}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.02 }}
                      onClick={() => onSelect?.(powerUp)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "8px 10px",
                        border: "none",
                        borderRadius: 10,
                        background: isSelected ? "var(--surface-selected)" : "transparent",
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
                        <div style={{ fontSize: "0.8rem", fontWeight: 650, color: "var(--text-primary)" }}>
                          {powerUp.label}
                        </div>
                        <div style={{ fontSize: "0.67rem", color: "var(--text-secondary)", marginTop: 1 }}>
                          {powerUp.description}
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: "0.6rem",
                          fontWeight: 700,
                          color: isSelected ? powerUp.color : "var(--text-tertiary)",
                          background: isSelected ? `${powerUp.color}1f` : "var(--surface-subtle)",
                          padding: "2px 8px",
                          borderRadius: 6,
                          fontFamily: "monospace",
                        }}
                      >
                        {powerUp.shortcut}
                      </span>
                    </motion.button>
                  );
                }

                if (isContext && isContextItem(item)) {
                  const ctx = item;
                  const Icon = ctx.icon;
                  return (
                    <motion.button
                      key={ctx.id}
                      type="button"
                      data-selected={isSelected}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.02 }}
                      onClick={() => onSelectContext?.(ctx)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "8px 10px",
                        border: "none",
                        borderRadius: 10,
                        background: isSelected ? "var(--surface-selected)" : "transparent",
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
                          background: `${ctx.color}16`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          border: isSelected ? `1px solid ${ctx.color}40` : "1px solid transparent",
                        }}
                      >
                        <Icon size={15} color={ctx.color} />
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "0.8rem", fontWeight: 650, color: "var(--text-primary)" }}>
                          {ctx.label}
                        </div>
                        <div style={{ fontSize: "0.67rem", color: "var(--text-secondary)", marginTop: 1 }}>
                          {ctx.description}
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: "0.6rem",
                          fontWeight: 700,
                          color: isSelected ? ctx.color : "var(--text-tertiary)",
                          background: isSelected ? `${ctx.color}1f` : "var(--surface-subtle)",
                          padding: "2px 8px",
                          borderRadius: 6,
                          fontFamily: "monospace",
                        }}
                      >
                        @{ctx.kind}
                      </span>
                    </motion.button>
                  );
                } else if (!isContext && !isContextItem(item)) {
                  const cmd = item;
                  const Icon = (cmd.icon && typeof cmd.icon === "function" ? cmd.icon : null) || COMMAND_ICONS[cmd.name] || Sparkles;
                  const cmdColor = cmd.color || COMMAND_COLORS[cmd.name] || "#F36F9C";
                  const cmdLabel = cmd.label || `/${cmd.name}`;
                  const cmdDescShort = cmd.descriptionShort || cmd.description || "";
                  const cmdDesc = cmd.description || cmd.descriptionShort || "";
                  const availabilityColor = (cmd.availability && AVAILABILITY_COLORS[cmd.availability]) || "#64748b";
                  const availabilityLabel = (cmd.availability && AVAILABILITY_LABELS[cmd.availability]) || "Ready";
                  return (
                    <motion.button
                      key={`${cmd.name}-${idx}`}
                      type="button"
                      data-selected={isSelected}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.02 }}
                      onClick={() => onSelectCommand?.(cmd)}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "flex-start",
                        gap: 4,
                        padding: "10px 12px",
                        border: "none",
                        borderRadius: 10,
                        background: isSelected ? "var(--surface-selected)" : "transparent",
                        cursor: "pointer",
                        width: "100%",
                        textAlign: "left",
                        fontFamily: "inherit",
                        transition: "background 0.12s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                        <span
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: 9,
                            background: `${cmdColor}16`,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                            border: isSelected ? `1px solid ${cmdColor}40` : "1px solid transparent",
                          }}
                        >
                          <Icon size={15} color={cmdColor} />
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: "0.8rem", fontWeight: 650, color: "var(--text-primary)" }}>
                            {cmdLabel}
                          </div>
                          <div style={{ fontSize: "0.67rem", color: "var(--text-secondary)", marginTop: 1 }}>
                            {cmdDescShort}
                          </div>
                        </div>
                        <span
                          style={{
                            fontSize: "0.6rem",
                            fontWeight: 700,
                            color: isSelected ? cmdColor : "var(--text-tertiary)",
                            background: isSelected ? `${cmdColor}1f` : "var(--surface-subtle)",
                            padding: "2px 8px",
                            borderRadius: 6,
                            fontFamily: "monospace",
                          }}
                        >
                          /{cmd.name}
                        </span>
                        <span
                          style={{
                            fontSize: "0.55rem",
                            fontWeight: 600,
                            color: availabilityColor,
                            background: `${availabilityColor}22`,
                            padding: "1px 6px",
                            borderRadius: 4,
                            fontFamily: "monospace",
                          }}
                        >
                          {availabilityLabel}
                        </span>
                      </div>
                      {cmdDesc && (
                        <div style={{ fontSize: "0.65rem", color: "var(--text-secondary)", width: "100%", paddingLeft: 42 }}>
                          {cmdDesc}
                        </div>
                      )}
                    </motion.button>
                  );
                }
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
            borderTop: "1px solid var(--border-subtle)",
            marginTop: 4,
          }}
        >
          <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>↑↓ navigate</span>
          <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>↵ select</span>
          <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>esc close</span>
          <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>Tab switch</span>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export default PowerUpMentions;