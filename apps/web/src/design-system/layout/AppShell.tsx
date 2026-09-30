import { useState, useCallback, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, History, Sun, Moon, X } from "lucide-react";
import { NavigationRail, type NavSection } from "./NavigationRail";
import { MobileNavigation } from "./MobileNavigation";
import { ConversationSidebar } from "./ConversationSidebar";

interface AppShellProps {
  children: ReactNode;
  isOnline?: boolean;
  activeSection?: NavSection;
  onNavigate?: (section: NavSection) => void;
  onNewChat?: () => void;
  onToggleHistory?: () => void;
  historyOpen?: boolean;
  activeConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
  hasClaudeAnswered?: boolean;
  isDark?: boolean;
  onToggleTheme?: () => void;
}

export function AppShell({
  children,
  isOnline = true,
  activeSection: controlledActiveSection,
  onNavigate,
  onNewChat,
  onToggleHistory,
  historyOpen = false,
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
  hasClaudeAnswered,
  isDark: externalIsDark,
  onToggleTheme: externalToggleTheme,
}: AppShellProps) {
  const [internalActiveSection, setInternalActiveSection] = useState<NavSection>("chat");
  const activeSection = controlledActiveSection ?? internalActiveSection;
  const [internalIsDark, setInternalIsDark] = useState(() => {
    if (typeof window !== "undefined") {
      return document.documentElement.getAttribute("data-theme") === "dark";
    }
    return false;
  });
  const isDark = externalIsDark !== undefined ? externalIsDark : internalIsDark;
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleTheme = externalToggleTheme ?? useCallback(() => {
    setInternalIsDark((prev) => {
      const next = !prev;
      document.documentElement.setAttribute("data-theme", next ? "dark" : "light");
      try {
        window.localStorage.setItem("hinaa-theme", next ? "dark" : "light");
      } catch { /* ok */ }
      return next;
    });
  }, []);

  const handleNavigate = useCallback((section: NavSection) => {
    if (onNavigate) {
      onNavigate(section);
    } else {
      setInternalActiveSection(section);
    }
    setMobileMenuOpen(false);
  }, [onNavigate]);

  return (
    <div
      className="sakura-app-shell"
      data-theme={isDark ? "dark" : "light"}
      style={{
        display: "flex",
        height: "100dvh",
        width: "100vw",
        overflow: "hidden",
        background: "transparent",
        color: "var(--text-primary)",
      }}
    >
      {/* Skip to content */}
      <a href="#main-content" className="skip-to-content">
        Skip to content
      </a>

      {/* Desktop Navigation Rail */}
      <NavigationRail
        active={activeSection}
        onNavigate={handleNavigate}
        onNewChat={onNewChat}
        onToggleHistory={onToggleHistory}
        historyOpen={historyOpen}
        isOnline={isOnline}
        isDark={isDark}
        onToggleTheme={toggleTheme}
        hasClaudeAnswered={hasClaudeAnswered}
      />

      {/* Conversation History Sidebar */}
      {onToggleHistory && (
        <ConversationSidebar
          isOpen={historyOpen}
          onClose={() => onToggleHistory()}
          activeConversationId={activeConversationId ?? null}
          onSelectConversation={(id) => {
            onSelectConversation?.(id);
            onToggleHistory();
          }}
          onDeleteConversation={onDeleteConversation}
          onNewChat={onNewChat}
        />
      )}

      {/* Main content area */}
      <main
        id="main-content"
        className="sakura-main-content hinaa-stage"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          minWidth: 0,
          minHeight: 0,
          boxSizing: "border-box",
          paddingBottom: "var(--hinaa-mobile-nav-clearance, 0px)",
        }}
      >
        {children}
      </main>

      {/* Mobile Navigation */}
      <MobileNavigation
        active={activeSection}
        onNavigate={handleNavigate}
        onOpenMore={() => setMobileMenuOpen(!mobileMenuOpen)}
      />

      {/* Mobile Drawer / Actions */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMobileMenuOpen(false)}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0, 0, 0, 0.5)",
              backdropFilter: "blur(4px)",
              WebkitBackdropFilter: "blur(4px)",
              zIndex: 1000,
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-end",
            }}
          >
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              style={{
                background: isDark ? "#121418" : "#ffffff",
                borderTop: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid #e2e8f0",
                borderTopLeftRadius: 20,
                borderTopRightRadius: 20,
                padding: "20px 16px max(24px, env(safe-area-inset-bottom))",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontWeight: 700, fontSize: 16 }}>Menu & Actions</span>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  style={{ background: "none", border: "none", padding: 4, cursor: "pointer", color: "var(--text-tertiary)" }}
                >
                  <X size={20} />
                </button>
              </div>
              {onNewChat && (
                <button
                  type="button"
                  onClick={() => {
                    onNewChat();
                    setMobileMenuOpen(false);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "12px 16px",
                    borderRadius: 12,
                    background: isDark ? "#ffffff" : "#1a232b",
                    color: isDark ? "#000000" : "#ffffff",
                    border: "none",
                    fontWeight: 650,
                    fontSize: 14,
                    cursor: "pointer",
                  }}
                >
                  <Plus size={18} />
                  <span>New Session</span>
                </button>
              )}
              {onToggleHistory && (
                <button
                  type="button"
                  onClick={() => {
                    onToggleHistory();
                    setMobileMenuOpen(false);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "12px 16px",
                    borderRadius: 12,
                    background: isDark ? "rgba(255, 255, 255, 0.06)" : "#f1f5f9",
                    color: "inherit",
                    border: "none",
                    fontWeight: 600,
                    fontSize: 14,
                    cursor: "pointer",
                  }}
                >
                  <History size={18} />
                  <span>Conversation History</span>
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  toggleTheme();
                  setMobileMenuOpen(false);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "12px 16px",
                  borderRadius: 12,
                  background: isDark ? "rgba(255, 255, 255, 0.06)" : "#f1f5f9",
                  color: "inherit",
                  border: "none",
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: "pointer",
                }}
              >
                {isDark ? <Sun size={18} /> : <Moon size={18} />}
                <span>{isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}</span>
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
