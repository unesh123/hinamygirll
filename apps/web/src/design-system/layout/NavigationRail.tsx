import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mic,
  MessageCircle,
  FolderKanban,
  Puzzle,
  Brain,
  Settings,
  Wrench,
  ChevronLeft,
  ChevronRight,
  Moon,
  Sun,
  Wifi,
  WifiOff,
  Image as ImageIcon,
  BookOpen,
  Plus,
  Clock,
} from "lucide-react";

export type NavSection =
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
  | "studio"
  | "settings";


interface NavItem {
  id: NavSection;
  label: string;
  icon: React.ReactNode;
  section: "primary" | "secondary";
}

const NAV_ITEMS: NavItem[] = [
  { id: "chat", label: "Chat", icon: <MessageCircle size={20} />, section: "primary" },
  { id: "images", label: "Images", icon: <ImageIcon size={20} />, section: "primary" },
  { id: "library", label: "Library", icon: <BookOpen size={20} />, section: "primary" },
  { id: "talk", label: "Talk", icon: <Mic size={20} />, section: "primary" },
  { id: "projects", label: "Projects", icon: <FolderKanban size={20} />, section: "primary" },
  { id: "creations", label: "Plugins & Skills", icon: <Puzzle size={20} />, section: "primary" },
  { id: "memory", label: "Memory", icon: <Brain size={20} />, section: "secondary" },
  { id: "settings", label: "Settings", icon: <Settings size={20} />, section: "secondary" },
];

interface NavigationRailProps {
  active: NavSection;
  onNavigate: (section: NavSection) => void;
  onNewChat?: () => void;
  onToggleHistory?: () => void;
  historyOpen?: boolean;
  isOnline?: boolean;
  isDark?: boolean;
  onToggleTheme?: () => void;
}

export function NavigationRail({
  active,
  onNavigate,
  onNewChat,
  onToggleHistory,
  historyOpen = false,
  isOnline = true,
  isDark = false,
  onToggleTheme,
}: NavigationRailProps) {
  const [expanded, setExpanded] = useState(false);
  const primaryItems = NAV_ITEMS.filter((i) => i.section === "primary");
  const secondaryItems = NAV_ITEMS.filter((i) => i.section === "secondary");

  return (
    <nav
      className="sakura-nav-rail"
      data-expanded={expanded}
      aria-label="HINAA navigation"
      style={{
        width: expanded ? "var(--nav-rail-expanded)" : "var(--nav-rail-width)",
      }}
    >
      {/* Logo */}
      <div className="sakura-nav-logo" style={{
        padding: expanded ? "var(--space-3) var(--space-4)" : "var(--space-3) 0",
        display: "flex",
        alignItems: "center",
        justifyContent: expanded ? "flex-start" : "center",
        gap: "var(--space-2)",
        marginBottom: "var(--space-2)",
      }}>
        <div style={{
          width: 32,
          height: 32,
          borderRadius: "var(--radius-md)",
          background: "linear-gradient(135deg, var(--accent), var(--peach))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontWeight: 800,
          fontSize: "var(--text-sm)",
          fontFamily: "var(--font-retro)",
          flexShrink: 0,
          boxShadow: "0 2px 8px var(--accent-glow)",
        }}>
          H
        </div>
        <AnimatePresence>
          {expanded && (
            <motion.span
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              style={{
                fontFamily: "var(--font-retro)",
                fontSize: "var(--text-sm)",
                fontWeight: 700,
                color: "var(--text-primary)",
                letterSpacing: "var(--tracking-wide)",
                whiteSpace: "nowrap",
              }}
            >
              HINAA
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* New Chat + History buttons */}
      <div style={{
        display: "flex",
        flexDirection: expanded ? "row" : "column",
        gap: "var(--space-1)",
        padding: expanded ? "0 var(--space-2)" : "0 var(--space-1-5)",
        marginBottom: "var(--space-2)",
        alignItems: "center",
      }}>
        {onNewChat && (
          <motion.button
            type="button"
            onClick={onNewChat}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            aria-label="New chat"
            title="New chat"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: expanded ? "flex-start" : "center",
              gap: "var(--space-2)",
              padding: expanded ? "var(--space-2) var(--space-3)" : "var(--space-2)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-default)",
              background: "var(--accent)",
              color: "#ffffff",
              cursor: "pointer",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              fontFamily: "var(--font-body)",
              width: expanded ? "100%" : 40,
              minHeight: 40,
              flex: expanded ? 1 : "none",
            }}
          >
            <Plus size={18} />
            <AnimatePresence>
              {expanded && (
                <motion.span
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  style={{ whiteSpace: "nowrap" }}
                >
                  New chat
                </motion.span>
              )}
            </AnimatePresence>
          </motion.button>
        )}
        {onToggleHistory && (
          <motion.button
            type="button"
            onClick={onToggleHistory}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            aria-label="Conversation history"
            title="Conversation history"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "var(--space-2)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-default)",
              background: historyOpen ? "var(--accent-pale)" : "transparent",
              color: historyOpen ? "var(--accent)" : "var(--text-tertiary)",
              cursor: "pointer",
              width: 40,
              minHeight: 40,
              flexShrink: 0,
            }}
          >
            <Clock size={18} />
          </motion.button>
        )}
      </div>

      {/* Primary nav */}
      <div className="sakura-nav-section" style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
        padding: expanded ? "0 var(--space-2)" : "0 var(--space-1-5)",
        flex: 1,
      }}>
        {primaryItems.map((item) => (
          <NavButton
            key={item.id}
            item={item}
            isActive={active === item.id}
            isExpanded={expanded}
            onClick={() => onNavigate(item.id)}
          />
        ))}
      </div>

      {/* Secondary nav */}
      <div className="sakura-nav-section" style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
        padding: expanded ? "0 var(--space-2)" : "0 var(--space-1-5)",
        borderTop: "1px solid var(--border-subtle)",
        paddingTop: "var(--space-3)",
      }}>
        {secondaryItems.map((item) => (
          <NavButton
            key={item.id}
            item={item}
            isActive={active === item.id}
            isExpanded={expanded}
            onClick={() => onNavigate(item.id)}
          />
        ))}
      </div>

      {/* Bottom controls */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
        padding: expanded ? "0 var(--space-2) var(--space-3)" : "0 var(--space-1-5) var(--space-3)",
        alignItems: "center",
      }}>
        {/* Connection status */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          padding: "var(--space-1-5) var(--space-2)",
          borderRadius: "var(--radius-sm)",
          fontSize: "var(--text-xs)",
          color: isOnline ? "var(--success)" : "var(--danger)",
          fontWeight: 500,
          width: expanded ? "100%" : "auto",
          justifyContent: expanded ? "flex-start" : "center",
        }}>
          {isOnline ? <Wifi size={14} /> : <WifiOff size={14} />}
          <AnimatePresence>
            {expanded && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {isOnline ? "Online" : "Offline"}
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 36,
            height: 36,
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-subtle)",
            background: "transparent",
            color: "var(--text-tertiary)",
            cursor: "pointer",
            transition: "all var(--duration-fast) var(--ease-standard)",
          }}
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 36,
            height: 36,
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-subtle)",
            background: "transparent",
            color: "var(--text-tertiary)",
            cursor: "pointer",
            transition: "all var(--duration-fast) var(--ease-standard)",
          }}
          title={expanded ? "Collapse navigation" : "Expand navigation"}
          aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
        >
          {expanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      <style>{`
        .sakura-nav-rail {
          display: flex;
          flex-direction: column;
          background: var(--bg-secondary);
          border-right: 1px solid var(--border-subtle);
          height: 100%;
          transition: width var(--duration-slow) var(--ease-soft);
          overflow: hidden;
          flex-shrink: 0;
          z-index: var(--z-raised);
        }

        @media (max-width: 768px) {
          .sakura-nav-rail {
            display: none;
          }
        }
      `}</style>
    </nav>
  );
}

function NavButton({
  item,
  isActive,
  isExpanded,
  onClick,
}: {
  item: NavItem;
  isActive: boolean;
  isExpanded: boolean;
  onClick: () => void;
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={item.label}
      aria-current={isActive ? "page" : undefined}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3)",
        padding: isExpanded ? "var(--space-2) var(--space-3)" : "var(--space-2)",
        borderRadius: "var(--radius-md)",
        border: "none",
        background: isActive ? "var(--accent-pale)" : "transparent",
        color: isActive ? "var(--accent)" : "var(--text-tertiary)",
        cursor: "pointer",
        fontSize: "var(--text-sm)",
        fontWeight: isActive ? 600 : 500,
        fontFamily: "var(--font-body)",
        transition: "background var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard)",
        justifyContent: isExpanded ? "flex-start" : "center",
        width: "100%",
        minHeight: 40,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {isActive && (
        <motion.div
          layoutId="nav-active-indicator"
          style={{
            position: "absolute",
            left: 0,
            top: "50%",
            transform: "translateY(-50%)",
            width: 3,
            height: 20,
            borderRadius: "var(--radius-pill)",
            background: "var(--accent)",
          }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
        />
      )}
      <span style={{ flexShrink: 0, display: "flex" }}>{item.icon}</span>
      <AnimatePresence>
        {isExpanded && (
          <motion.span
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            style={{ whiteSpace: "nowrap" }}
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
