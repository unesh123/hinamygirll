import { useState, useCallback, type ReactNode } from "react";
import { NavigationRail, type NavSection } from "./NavigationRail";
import { MobileNavigation } from "./MobileNavigation";

interface AppShellProps {
  children: ReactNode;
  isOnline?: boolean;
}

export function AppShell({ children, isOnline = true }: AppShellProps) {
  const [activeSection, setActiveSection] = useState<NavSection>("chat");
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
    setActiveSection(section);
    setMobileMenuOpen(false);
  }, []);

  return (
    <div
      className="sakura-app-shell"
      data-theme={isDark ? "dark" : "light"}
      style={{
        display: "flex",
        height: "100dvh",
        width: "100vw",
        overflow: "hidden",
        background: "var(--bg-primary)",
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
        isOnline={isOnline}
        isDark={isDark}
        onToggleTheme={toggleTheme}
      />

      {/* Main content area */}
      <main
        id="main-content"
        className="sakura-main-content"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          minWidth: 0,
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
