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
  Settings, Monitor, GitBranch, Wand2, type LucideIcon,
} from "lucide-react";

export type TriggerType = "@" | "/";

/** @deprecated Use ContextItem | CommandItem instead */
export interface PowerUp {
  id: string;
  icon: LucideIcon;
  label: string;
  shortcut: string;
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

interface PowerUpMentionsProps {
  visible: boolean;
  filter: string;
  onSelectContext: (context: ContextItem) => void;
  onSelectCommand: (command: CommandItem, args?: string) => void;
  onClose: () => void;
  trigger: TriggerType;
  contexts: ContextItem[];
  commands: CommandItem[];
}

export function PowerUpMentions({
  visible,
  filter,
  onSelectContext,
  onSelectCommand,
  onClose,
  trigger,
  contexts,
  commands,
}: PowerUpMentionsProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"contexts" | "commands">(trigger === "@" ? "contexts" : "commands");
  const containerRef = useRef<HTMLDivElement>(null);

  // Follow trigger changes: the palette stays mounted, so "@" must always
  // show contexts and "/" must always show commands.
  useEffect(() => {
    setActiveTab(trigger === "@" ? "contexts" : "commands");
  }, [trigger]);

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

  const activeItems = activeTab === "contexts" ? filteredContexts : filteredCommands;

  // Reset selection when filter or tab changes
  useEffect(() => { setSelectedIndex(0); }, [filter, activeTab]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible) return;
      
      // Tab to switch between contexts and commands
      if (e.key === "Tab") {
        e.preventDefault();
        setActiveTab((prev) => (prev === "contexts" ? "commands" : "contexts"));
        return;
      }
      
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, activeItems.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && activeItems[selectedIndex]) {
        e.preventDefault();
        const item = activeItems[selectedIndex];
        if (activeTab === "contexts") {
          onSelectContext(item as ContextItem);
        } else {
          onSelectCommand(item as CommandItem);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    },
    [visible, activeItems, selectedIndex, activeTab, onSelectContext, onSelectCommand, onClose],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Scroll selected into view
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const selected = container.querySelector("[data-selected='true']") as HTMLElement | null;
    if (selected) {
      selected.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [selectedIndex]);

  // Group items
  const groups = useMemo(() => {
    const map = new Map<string, (ContextItem | CommandItem)[]>();
    for (const item of activeItems) {
      const group = "group" in item && item.group ? item.group : ("name" in item ? (COMMAND_GROUPS[item.name] || "Commands") : (item.kind || "Context"));
      const list = map.get(group) || [];
      list.push(item);
      map.set(group, list);
    }
    return Array.from(map.entries());
  }, [activeItems]);

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
          background: "linear-gradient(145deg, rgba(55,38,54,.98), rgba(28,18,33,.99))",
          backdropFilter: "blur(28px)",
          WebkitBackdropFilter: "blur(28px)",
          borderRadius: 18,
          border: "1px solid rgba(255,202,218,.22)",
          boxShadow: "0 18px 60px rgba(4,2,5,.42), inset 0 1px rgba(255,255,255,.06)",
          padding: "10px 8px",
          zIndex: 200,
          width: "min(400px, calc(100vw - 24px))",
          maxHeight: 480,
          overflow: "hidden",
        }}
      >
        {/* Tab bar */}
        <div style={{ display: "flex", gap: 4, marginBottom: 8, padding: "0 4px" }}>
          <button
            type="button"
            onClick={() => setActiveTab("contexts")}
            style={{
              flex: 1,
              padding: "6px 12px",
              borderRadius: 8,
              border: "none",
              background: activeTab === "contexts" ? "rgba(238,145,173,.16)" : "transparent",
              color: activeTab === "contexts" ? "#ffd4e0" : "#c9aeba",
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
              background: activeTab === "commands" ? "rgba(238,145,173,.16)" : "transparent",
              color: activeTab === "commands" ? "#ffd4e0" : "#c9aeba",
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

        <div
          ref={containerRef}
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
                  color: "#c9aeba",
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
                      onClick={() => onSelectContext(ctx)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "8px 10px",
                        border: "none",
                        borderRadius: 10,
                        background: isSelected ? "rgba(238,145,173,.16)" : "transparent",
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
                        <div style={{ fontSize: "0.8rem", fontWeight: 650, color: "#fff4f8" }}>
                          {ctx.label}
                        </div>
                        <div style={{ fontSize: "0.67rem", color: "#c9aeba", marginTop: 1 }}>
                          {ctx.description}
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: "0.6rem",
                          fontWeight: 700,
                          color: isSelected ? "#ffd4e0" : "#c9aeba",
                          background: isSelected ? `${ctx.color}22` : "rgba(255,255,255,.055)",
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
                      onClick={() => onSelectCommand(cmd)}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "flex-start",
                        gap: 4,
                        padding: "10px 12px",
                        border: "none",
                        borderRadius: 10,
                        background: isSelected ? "rgba(238,145,173,.16)" : "transparent",
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
                          <div style={{ fontSize: "0.8rem", fontWeight: 650, color: "#fff4f8" }}>
                            {cmdLabel}
                          </div>
                          <div style={{ fontSize: "0.67rem", color: "#c9aeba", marginTop: 1 }}>
                            {cmdDescShort}
                          </div>
                        </div>
                        <span
                          style={{
                            fontSize: "0.6rem",
                            fontWeight: 700,
                            color: isSelected ? "#ffd4e0" : "#c9aeba",
                            background: isSelected ? `${cmdColor}22` : "rgba(255,255,255,.055)",
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
                        <div style={{ fontSize: "0.65rem", color: "#c9aeba", width: "100%", paddingLeft: 42 }}>
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
            borderTop: "1px solid rgba(255,218,231,.12)",
            marginTop: 4,
          }}
        >
          <span style={{ fontSize: "0.62rem", color: "#c9aeba" }}>↑↓ navigate</span>
          <span style={{ fontSize: "0.62rem", color: "#c9aeba" }}>↵ select</span>
          <span style={{ fontSize: "0.62rem", color: "#c9aeba" }}>esc close</span>
          <span style={{ fontSize: "0.62rem", color: "#c9aeba" }}>Tab switch</span>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export default PowerUpMentions;