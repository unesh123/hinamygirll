import React, { useState, useEffect } from "react";
import {
  FolderGit2,
  Target,
  Search,
  Sparkles,
  MessageSquare,
  Briefcase,
  SlidersHorizontal,
  Sun,
  Moon,
  CheckCircle2,
  ChevronDown,
  X,
} from "lucide-react";

export type WorkspaceMode = "talk" | "work" | "operate";

export interface TopBarV6Props {
  currentMode: WorkspaceMode;
  onModeChange: (mode: WorkspaceMode) => void;
  activeProject?: { id: string; name: string; repo?: string } | null;
  activeGoal?: { id: string; title: string; criteriaCount?: number } | null;
  activeProviderName?: string;
  isOnline?: boolean;
  isDark?: boolean;
  onToggleTheme?: () => void;
  onOpenSearch?: () => void;
  onOpenProjectSettings?: () => void;
  onOpenGoalDetails?: () => void;
}

export const TopBarV6: React.FC<TopBarV6Props> = ({
  currentMode,
  onModeChange,
  activeProject = { id: "default", name: "HINAA Workspace", repo: "main" },
  activeGoal,
  activeProviderName = "Auto (Frontier)",
  isOnline = true,
  isDark = false,
  onToggleTheme,
  onOpenSearch,
  onOpenProjectSettings,
  onOpenGoalDetails,
}) => {
  const [goalPopoverOpen, setGoalPopoverOpen] = useState(false);

  // Keyboard shortcut listener for Ctrl+K / Cmd+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenSearch?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpenSearch]);

  return (
    <header
      className="topbar-v6"
      style={{
        height: "var(--topbar-height, 52px)",
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 16px",
        background: "var(--surface-glass, rgba(255, 255, 255, 0.85))",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.08))",
        zIndex: 40,
        userSelect: "none",
      }}
    >
      {/* ── Left: Project Pill & Goal Pill ──────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        {/* Project Pill */}
        <button
          type="button"
          onClick={onOpenProjectSettings}
          className="topbar-project-pill"
          title="Active Project Workspace"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 12px",
            borderRadius: "var(--radius-full, 9999px)",
            background: "var(--surface-subtle, #f6f3f7)",
            border: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.08))",
            color: "var(--text-primary, #1e191d)",
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
            transition: "all 0.15s ease",
            whiteSpace: "nowrap",
          }}
        >
          <FolderGit2 size={14} style={{ color: "var(--accent-primary, #dc5f8b)" }} />
          <span>{activeProject?.name || "Workspace"}</span>
          <ChevronDown size={12} style={{ opacity: 0.6 }} />
        </button>

        {/* Goal Pill (if active) */}
        {activeGoal ? (
          <div style={{ position: "relative" }}>
            <button
              type="button"
              onClick={() => setGoalPopoverOpen(!goalPopoverOpen)}
              className="topbar-goal-pill"
              title="Active Persistent Goal"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 12px",
                borderRadius: "var(--radius-full, 9999px)",
                background: "var(--accent-subtle, #fff2f6)",
                border: "1px solid var(--border-accent, rgba(220, 95, 139, 0.35))",
                color: "var(--accent-primary, #dc5f8b)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease",
                maxWidth: 220,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              <Target size={13} />
              <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                {activeGoal.title}
              </span>
              <ChevronDown size={11} style={{ opacity: 0.7 }} />
            </button>

            {/* Goal Preview Popover */}
            {goalPopoverOpen && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  left: 0,
                  width: 280,
                  padding: 14,
                  background: "var(--surface-overlay, #ffffff)",
                  borderRadius: "var(--radius-md, 12px)",
                  boxShadow: "var(--shadow-dropdown, 0 10px 25px -5px rgba(0,0,0,0.1))",
                  border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
                  zIndex: 50,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--accent-primary)" }}>
                    ACTIVE GOAL
                  </div>
                  <button
                    onClick={() => setGoalPopoverOpen(false)}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)" }}
                  >
                    <X size={14} />
                  </button>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  {activeGoal.title}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 10 }}>
                  {activeGoal.criteriaCount ? `${activeGoal.criteriaCount} acceptance criteria tracked` : "Continuous goal tracking active"}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setGoalPopoverOpen(false);
                    onOpenGoalDetails?.();
                  }}
                  style={{
                    width: "100%",
                    padding: "6px 12px",
                    background: "var(--accent-primary)",
                    color: "#fff",
                    border: "none",
                    borderRadius: "var(--radius-sm, 8px)",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  View Goal Specs
                </button>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* ── Center: Workspace Mode Switcher (Talk / Work / Operate) ──────── */}
      <div
        className="topbar-mode-switcher"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          padding: 3,
          borderRadius: "var(--radius-full, 9999px)",
          background: "var(--surface-subtle, #f6f3f7)",
          border: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.08))",
        }}
      >
        <button
          type="button"
          onClick={() => onModeChange("talk")}
          className={`mode-tab ${currentMode === "talk" ? "active" : ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 14px",
            borderRadius: "var(--radius-full, 9999px)",
            border: "none",
            fontSize: 13,
            fontWeight: currentMode === "talk" ? 600 : 500,
            background: currentMode === "talk" ? "var(--surface-card, #ffffff)" : "transparent",
            color: currentMode === "talk" ? "var(--accent-primary, #dc5f8b)" : "var(--text-secondary, #5e545d)",
            boxShadow: currentMode === "talk" ? "var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))" : "none",
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          <MessageSquare size={13} />
          <span>Talk</span>
        </button>

        <button
          type="button"
          onClick={() => onModeChange("work")}
          className={`mode-tab ${currentMode === "work" ? "active" : ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 14px",
            borderRadius: "var(--radius-full, 9999px)",
            border: "none",
            fontSize: 13,
            fontWeight: currentMode === "work" ? 600 : 500,
            background: currentMode === "work" ? "var(--surface-card, #ffffff)" : "transparent",
            color: currentMode === "work" ? "var(--accent-primary, #dc5f8b)" : "var(--text-secondary, #5e545d)",
            boxShadow: currentMode === "work" ? "var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))" : "none",
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          <Briefcase size={13} />
          <span>Work</span>
        </button>

        <button
          type="button"
          onClick={() => onModeChange("operate")}
          className={`mode-tab ${currentMode === "operate" ? "active" : ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 14px",
            borderRadius: "var(--radius-full, 9999px)",
            border: "none",
            fontSize: 13,
            fontWeight: currentMode === "operate" ? 600 : 500,
            background: currentMode === "operate" ? "var(--surface-card, #ffffff)" : "transparent",
            color: currentMode === "operate" ? "var(--accent-primary, #dc5f8b)" : "var(--text-secondary, #5e545d)",
            boxShadow: currentMode === "operate" ? "var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))" : "none",
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          <SlidersHorizontal size={13} />
          <span>Operate</span>
        </button>
      </div>

      {/* ── Right: Global Search, Provider Pill, Theme Toggle ─────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {/* Global Search Button */}
        <button
          type="button"
          onClick={onOpenSearch}
          className="topbar-search-btn"
          title="Search conversation, files, and tools (Ctrl+K)"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "5px 12px",
            borderRadius: "var(--radius-full, 9999px)",
            background: "var(--surface-subtle, #f6f3f7)",
            border: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.08))",
            color: "var(--text-tertiary, #847a83)",
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          <Search size={13} />
          <span className="hidden sm:inline">Search...</span>
          <kbd
            style={{
              padding: "1px 5px",
              background: "var(--surface-card, #ffffff)",
              border: "1px solid var(--border-subtle, rgba(0,0,0,0.1))",
              borderRadius: "var(--radius-xs, 4px)",
              fontSize: 10,
              fontWeight: 600,
              color: "var(--text-muted)",
            }}
          >
            ⌘K
          </kbd>
        </button>

        {/* Provider Indicator Pill */}
        <div
          title={`Active Engine: ${activeProviderName}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            padding: "4px 10px",
            borderRadius: "var(--radius-full, 9999px)",
            background: "var(--surface-subtle, #f6f3f7)",
            fontSize: 12,
            color: "var(--text-secondary, #5e545d)",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: isOnline ? "var(--semantic-success-fg, #15803d)" : "var(--semantic-warning-fg, #b45309)",
            }}
          />
          <span style={{ maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {activeProviderName}
          </span>
        </div>

        {/* Dark Mode Toggle */}
        {onToggleTheme && (
          <button
            type="button"
            onClick={onToggleTheme}
            className="topbar-theme-toggle"
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "transparent",
              border: "1px solid var(--border-subtle, rgba(0, 0, 0, 0.08))",
              color: "var(--text-secondary, #5e545d)",
              cursor: "pointer",
            }}
          >
            {isDark ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        )}
      </div>
    </header>
  );
};
