import { useState, useCallback, type ReactNode } from "react";
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
}: AppShellProps) {
  const [internalActiveSection, setInternalActiveSection] = useState<NavSection>("chat");
  const activeSection = controlledActiveSection ?? internalActiveSection;
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== "undefined") {
      return document.documentElement.getAttribute("data-theme") === "dark";
    }
    return false;
  });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleTheme = useCallback(() => {
    setIsDark((prev) => {
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
    </div>
  );
}
