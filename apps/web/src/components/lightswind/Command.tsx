// Command — Hinaa Command Center (adapted from lightswind.com)
// Cmd+K global command palette with search, keyboard nav, and Hinaa-specific actions

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Loader2, Settings, Mic, PlayCircle, Globe, MessageCircle, Sparkles } from "lucide-react";

// ── Context ───────────────────────────────────────────────────────────────
interface CommandCtx {
  query: string;
  setQuery: (q: string) => void;
  selectedIndex: number;
  setSelectedIndex: React.Dispatch<React.SetStateAction<number>>;
  itemIds: string[];
  registerItem: (id: string) => void;
  unregisterItem: (id: string) => void;
}
const CommandContext = React.createContext<CommandCtx | undefined>(undefined);
const useCommand = () => {
  const ctx = React.useContext(CommandContext);
  if (!ctx) throw new Error("useCommand must be inside Command");
  return ctx;
};

// ── Root ─────────────────────────────────────────────────────────────────
export const Command = React.forwardRef<HTMLDivElement, { children: React.ReactNode; className?: string }>(
  ({ children, className = "" }, ref) => {
    const [query, setQuery] = React.useState("");
    const [selectedIndex, setSelectedIndex] = React.useState(0);
    const [itemIds, setItemIds] = React.useState<string[]>([]);

    const registerItem = React.useCallback((id: string) => {
      setItemIds(prev => prev.includes(id) ? prev : [...prev, id]);
    }, []);
    const unregisterItem = React.useCallback((id: string) => {
      setItemIds(prev => prev.filter(i => i !== id));
    }, []);

    React.useEffect(() => { setSelectedIndex(0); }, [query]);

    return (
      <CommandContext.Provider value={{ query, setQuery, selectedIndex, setSelectedIndex, itemIds, registerItem, unregisterItem }}>
        <div ref={ref} className={`hinaa-command ${className}`}>{children}</div>
      </CommandContext.Provider>
    );
  }
);
Command.displayName = "Command";

// ── Dialog ────────────────────────────────────────────────────────────────
export function CommandDialog({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (open) document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="command-dialog-overlay" onClick={onClose}>
          <motion.div
            className="command-dialog-container"
            onClick={e => e.stopPropagation()}
            initial={{ opacity: 0, scale: 0.92, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: -20 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
          >
            <Command>{children}</Command>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

// ── Input ─────────────────────────────────────────────────────────────────
export const CommandInput = React.forwardRef<HTMLInputElement, { placeholder?: string; isLoading?: boolean }>(
  ({ placeholder = "Ask Hinaa anything…", isLoading }, ref) => {
    const { query, setQuery, itemIds, selectedIndex, setSelectedIndex } = useCommand();

    const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIndex(p => itemIds.length > 0 ? (p + 1) % itemIds.length : 0); }
      if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIndex(p => itemIds.length > 0 ? (p - 1 + itemIds.length) % itemIds.length : 0); }
      if (e.key === "Enter") {
        e.preventDefault();
        const el = document.querySelector(`[data-cmd-id="${itemIds[selectedIndex]}"]`) as HTMLElement;
        el?.click();
      }
    };

    return (
      <div className="command-input-row">
        {isLoading ? <Loader2 className="command-search-icon spinning" size={16} /> : <Search className="command-search-icon" size={16} />}
        <input
          ref={ref}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={onKey}
          className="command-input"
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          autoFocus
        />
        <kbd className="command-esc-badge">ESC</kbd>
      </div>
    );
  }
);
CommandInput.displayName = "CommandInput";

// ── List ──────────────────────────────────────────────────────────────────
export const CommandList = React.forwardRef<HTMLDivElement, { children: React.ReactNode; className?: string }>(
  ({ children, className = "" }, ref) => (
    <div ref={ref} className={`command-list ${className}`}>{children}</div>
  )
);
CommandList.displayName = "CommandList";

// ── Group ─────────────────────────────────────────────────────────────────
export const CommandGroup = React.forwardRef<HTMLDivElement, { heading?: string; children: React.ReactNode; className?: string }>(
  ({ heading, children, className = "" }, ref) => (
    <div ref={ref} className={`command-group ${className}`}>
      {heading && <div className="command-group-heading">{heading}</div>}
      {children}
    </div>
  )
);
CommandGroup.displayName = "CommandGroup";

// ── Item ──────────────────────────────────────────────────────────────────
export const CommandItem = React.forwardRef<HTMLDivElement, {
  children: React.ReactNode;
  onSelect?: () => void;
  disabled?: boolean;
  className?: string;
  keywords?: string[];
}>(({ children, onSelect, disabled, className = "", keywords }, ref) => {
  const { query, registerItem, unregisterItem, itemIds, selectedIndex, setSelectedIndex } = useCommand();
  const id = React.useId();

  React.useEffect(() => { registerItem(id); return () => unregisterItem(id); }, [id, registerItem, unregisterItem]);

  const isVisible = !query || keywords?.some(k => k.toLowerCase().includes(query.toLowerCase())) ||
    (typeof children === "string" && children.toLowerCase().includes(query.toLowerCase()));

  if (!isVisible) return null;
  const isFocused = itemIds[selectedIndex] === id;

  return (
    <motion.div
      ref={ref}
      data-cmd-id={id}
      className={`command-item ${isFocused ? "focused" : ""} ${disabled ? "disabled" : ""} ${className}`}
      onMouseEnter={() => { const i = itemIds.indexOf(id); if (i !== -1) setSelectedIndex(i); }}
      onClick={() => { if (!disabled && onSelect) onSelect(); }}
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.15 }}
    >
      {children}
    </motion.div>
  );
});
CommandItem.displayName = "CommandItem";

// ── Separator ─────────────────────────────────────────────────────────────
export function CommandSeparator() {
  return <div className="command-separator" />;
}

// ── Empty ─────────────────────────────────────────────────────────────────
export function CommandEmpty({ children }: { children?: React.ReactNode }) {
  return (
    <div className="command-empty">
      <Search size={20} className="command-empty-icon" />
      <p>{children || "No results found."}</p>
    </div>
  );
}

// ── Shortcut badge ────────────────────────────────────────────────────────
export function CommandShortcut({ children }: { children: React.ReactNode }) {
  return <span className="command-shortcut">{children}</span>;
}

// ── Hinaa Command Center ──────────────────────────────────────────────────
// A pre-built command palette specific to Hinaa with common actions

interface HinaaCommandProps {
  open: boolean;
  onClose: () => void;
  onAction: (action: string, payload?: string) => void;
  companionName?: string;
}

const HINAA_COMMANDS = [
  { id: "start-voice", label: "Start voice chat", icon: Mic, shortcut: "V", color: "#8b5cf6", keywords: ["voice", "speak", "talk", "mic"] },
  { id: "play-music", label: "Play music on YouTube", icon: PlayCircle, shortcut: "M", color: "#ef4444", keywords: ["music", "play", "youtube", "song"] },
  { id: "search-web", label: "Search the web", icon: Globe, shortcut: "S", color: "#06b6d4", keywords: ["search", "google", "find", "web"] },
  { id: "generate-image", label: "Generate an image", icon: Sparkles, shortcut: "I", color: "#f59e0b", keywords: ["image", "picture", "generate", "create"] },
  { id: "new-chat", label: "New conversation", icon: MessageCircle, shortcut: "N", color: "#10b981", keywords: ["new", "chat", "conversation", "start"] },
  { id: "open-settings", label: "Open settings", icon: Settings, shortcut: ",", color: "#64748b", keywords: ["settings", "config", "preferences"] },
];

export function HinaaCommandCenter({ open, onClose, onAction, companionName = "Hinaa" }: HinaaCommandProps) {
  return (
    <CommandDialog open={open} onClose={onClose}>
      <CommandInput placeholder={`Ask ${companionName} anything… (↑↓ to navigate)`} />
      <CommandList>
        <CommandGroup heading="Quick Actions">
          {HINAA_COMMANDS.map(cmd => {
            const Icon = cmd.icon;
            return (
              <CommandItem
                key={cmd.id}
                keywords={cmd.keywords}
                onSelect={() => { onAction(cmd.id); onClose(); }}
              >
                <span className="command-item-icon" style={{ color: cmd.color }}><Icon size={16} /></span>
                <span className="command-item-label">{cmd.label}</span>
                <CommandShortcut>⌘{cmd.shortcut}</CommandShortcut>
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
