import React from "react";
import {
  MessageSquare,
  Brain,
  FileText,
  Search,
  ChevronDown,
  Bell,
  Sun,
  Moon,
  Settings,
  Sparkles,
} from "lucide-react";
import { ModelSelectorV7 } from "../chat/ModelSelectorV7";
import { useCapabilities } from "../../features/providers/hooks/useCapabilities";

export type WorkspaceMode = "talk" | "work" | "operate" | "showroom" | "vault";
export type ExecutiveMode = "chat" | "deep-reasoning" | "report" | "research";

export interface TopBarV6Props {
  currentMode: WorkspaceMode;
  onModeChange: (mode: WorkspaceMode) => void;
  activeProject?: { id: string; name: string; repo?: string } | null;
  activeGoal?: { id: string; title: string; criteriaCount?: number } | null;
  isDark?: boolean;
  onToggleTheme?: () => void;
  onOpenSearch?: () => void;
  onOpenProjectSettings?: () => void;
  onOpenGoalDetails?: () => void;
  onSelectModel?: (modelId: string, providerId: string) => void;
  selectedModelId?: string | null;
  executiveMode: ExecutiveMode;
  onExecutiveModeChange: (mode: ExecutiveMode) => void;
}

export const TopBarV6: React.FC<TopBarV6Props> = ({
  currentMode,
  onModeChange,
  activeProject = { id: "default", name: "HINA Workspace", repo: "main" },
  isDark = false,
  onToggleTheme,
  onOpenSearch,
  onSelectModel,
  selectedModelId,
  executiveMode,
  onExecutiveModeChange,
}) => {
  const { models, providers, runtime } = useCapabilities();
  // Derived, not copied: a local snapshot kept showing "Auto (Router)" after
  // the model had been chosen somewhere else.
  const isAuto = !selectedModelId;

  const handleModeClick = (mode: ExecutiveMode) => {
    onExecutiveModeChange(mode);
    onModeChange("work");
  };

  return (
    <header
      className="topbar-v6"
      data-testid="executive-topbar"
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "rgba(0, 0, 0, 0.78)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
        borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.1))",
        zIndex: 25,
        userSelect: "none",
        fontFamily: "var(--font-control, ui-sans-serif, system-ui, sans-serif)",
        padding: "0 16px",
        height: "52px",
      }}
    >
      {/* ── Left: Breadcrumb ────────────────────────────── */}
      <div className="topbar-v6__breadcrumb" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button
          type="button"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            background: "transparent",
            border: "none",
            color: "var(--color-twilight-blue, #426188)",
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
            padding: 0,
            fontFamily: "inherit",
          }}
        >
          <span>Workspace</span>
          <ChevronDown size={12} style={{ opacity: 0.7 }} />
        </button>
        <span style={{ color: "rgba(255, 255, 255, 0.2)", fontSize: 13 }}>/</span>
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-whiteout, #ffffff)", letterSpacing: "0.02em" }}>
          Intelligence
        </span>
      </div>

      {/* ── Center: Executive Modes Pills (Air Pill Toggle Buttons) ──────────────── */}
      <div
        className="topbar-v6__modes"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          background: "rgba(255, 255, 255, 0.06)",
          padding: "3px 4px",
          borderRadius: "var(--radius-pills, 9999px)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
        }}
      >
        <button
          type="button"
          data-testid="mode-chat"
          onClick={() => handleModeClick("chat")}
          className="topbar-v6__mode-btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            borderRadius: 9999,
            border: "none",
            fontWeight: 500,
            fontSize: 12,
            padding: "5px 12px",
            background: executiveMode === "chat" ? "var(--color-haze, #f5f5f5)" : "transparent",
            color: executiveMode === "chat" ? "var(--color-ink, #1b1b1b)" : "rgba(255, 255, 255, 0.72)",
            cursor: "pointer",
            transition: "all 0.14s ease",
            fontFamily: "inherit",
          }}
        >
          <MessageSquare size={13} />
          <span>Chat</span>
        </button>

        <button
          type="button"
          data-testid="mode-deep-reasoning"
          onClick={() => handleModeClick("deep-reasoning")}
          className="topbar-v6__mode-btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            borderRadius: 9999,
            border: "none",
            fontWeight: 500,
            fontSize: 12,
            padding: "5px 12px",
            background: executiveMode === "deep-reasoning" ? "var(--color-haze, #f5f5f5)" : "transparent",
            color: executiveMode === "deep-reasoning" ? "var(--color-ink, #1b1b1b)" : "rgba(255, 255, 255, 0.72)",
            cursor: "pointer",
            transition: "all 0.14s ease",
            fontFamily: "inherit",
          }}
        >
          <Brain size={13} />
          <span>Reasoning</span>
        </button>
        <button
          type="button"
          data-testid="mode-report"
          onClick={() => handleModeClick("report")}
          className="topbar-v6__mode-btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            borderRadius: 9999,
            border: "none",
            fontWeight: 500,
            fontSize: 12,
            padding: "5px 12px",
            background: executiveMode === "report" ? "var(--color-haze, #f5f5f5)" : "transparent",
            color: executiveMode === "report" ? "var(--color-ink, #1b1b1b)" : "rgba(255, 255, 255, 0.72)",
            cursor: "pointer",
            transition: "all 0.14s ease",
            fontFamily: "inherit",
          }}
        >
          <FileText size={13} />
          <span>Report</span>
        </button>

        <button
          type="button"
          data-testid="mode-research"
          onClick={() => handleModeClick("research")}
          className="topbar-v6__mode-btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            borderRadius: 9999,
            border: "none",
            fontWeight: 500,
            fontSize: 12,
            padding: "5px 12px",
            background: executiveMode === "research" ? "var(--color-haze, #f5f5f5)" : "transparent",
            color: executiveMode === "research" ? "var(--color-ink, #1b1b1b)" : "rgba(255, 255, 255, 0.72)",
            cursor: "pointer",
            transition: "all 0.14s ease",
            fontFamily: "inherit",
          }}
        >
          <Search size={13} />
          <span>Research</span>
        </button>
      </div>

      {/* ── Right: Real Model Selector & Actions ─── */}
      <div className="topbar-v6__actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {/* Real Model Selector V7 */}
        <ModelSelectorV7
          models={models}
          providers={providers}
          selectedModelId={selectedModelId}
          isAutoRouter={isAuto}
          onSelectAuto={() => onSelectModel?.("auto", "auto")}
          onSelectModel={(model) => onSelectModel?.(model.id, model.provider)}
          backendConnected={runtime.backendConnected}
        />
        {/* Runway 3D Showroom Ghost Button */}
        <button
          type="button"
          data-testid="topbar-showroom-btn"
          onClick={() => onModeChange(currentMode === "showroom" ? "work" : "showroom")}
          title="Haute-Couture 3D Runway Showroom"
          className={currentMode === "showroom" ? "air-solid-btn" : "air-ghost-btn"}
          style={{
            height: 32,
            padding: "0 12px",
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Sparkles size={13} />
          <span>Runway 3D</span>
        </button>

        {/* Search button */}
        <button
          type="button"
          onClick={onOpenSearch}
          title="Search (⌘K)"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            background: "#ffffff",
            color: "#64748b",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <Search size={14} />
        </button>

        {/* Notification Bell */}
        <button
          type="button"
          title="Notifications"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            background: "#ffffff",
            color: "#64748b",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <Bell size={14} />
        </button>

        {/* Theme Sun */}
        {onToggleTheme && (
          <button
            type="button"
            onClick={onToggleTheme}
            title={isDark ? "Light Mode" : "Dark Mode"}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
              color: "#64748b",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            {isDark ? <Moon size={14} /> : <Sun size={14} />}
          </button>
        )}

        {/* User Initials Circle */}
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 9999,
            background: "#fecdd3",
            color: "#be123c",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          AM
        </div>
      </div>
    </header>
  );
};
