import React, { useState } from "react";
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
} from "lucide-react";
import { ModelSelectorV7 } from "../chat/ModelSelectorV7";
import { useCapabilities } from "../../features/providers/hooks/useCapabilities";

export type WorkspaceMode = "talk" | "work" | "operate";
export type ExecutiveMode = "chat" | "deep-reasoning" | "report" | "research";

export interface TopBarV6Props {
  currentMode: WorkspaceMode;
  onModeChange: (mode: WorkspaceMode) => void;
  activeProject?: { id: string; name: string; repo?: string } | null;
  activeGoal?: { id: string; title: string; criteriaCount?: number } | null;
  activeProviderName?: string;
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
  const [isAuto, setIsAuto] = useState(!selectedModelId);

  const handleModeClick = (mode: ExecutiveMode) => {
    onExecutiveModeChange(mode);
    if (!(mode === "chat" && currentMode === "talk")) onModeChange("work");
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
        background: "#ffffff",
        borderBottom: "1px solid #e2e8f0",
        zIndex: 25,
        userSelect: "none",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
      }}
    >
      {/* ── Left: Breadcrumb ────────────────────────────── */}
      <div className="topbar-v6__breadcrumb">
        <button
          type="button"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            background: "transparent",
            border: "none",
            color: "#64748b",
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
            padding: 0,
          }}
        >
          <span>Workspace</span>
          <ChevronDown size={12} style={{ opacity: 0.7 }} />
        </button>
        <span style={{ color: "#cbd5e1", fontSize: 13 }}>/</span>
        <span style={{ fontSize: 13, fontWeight: 650, color: "#0f172a" }}>
          Chat
        </span>
      </div>

      {/* ── Center: Executive Modes Pills ──────────────── */}
      <div
        className="topbar-v6__modes"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          background: "#f8fafc",
          padding: "3px 4px",
          borderRadius: 10,
          border: "1px solid #f1f5f9",
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
            borderRadius: 7,
            border: "none",
            fontWeight: executiveMode === "chat" ? 600 : 500,
            background: executiveMode === "chat" ? "#1a232b" : "transparent",
            color: executiveMode === "chat" ? "#ffffff" : "#64748b",
            cursor: "pointer",
            transition: "all 0.12s ease",
            boxShadow: executiveMode === "chat" ? "0 1px 2px rgba(0,0,0,0.1)" : "none",
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
            borderRadius: 7,
            border: "none",
            fontWeight: executiveMode === "deep-reasoning" ? 600 : 500,
            background: executiveMode === "deep-reasoning" ? "#1a232b" : "transparent",
            color: executiveMode === "deep-reasoning" ? "#ffffff" : "#64748b",
            cursor: "pointer",
            transition: "all 0.12s ease",
          }}
        >
          <Brain size={13} />
          <span>Deep Reasoning</span>
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
            borderRadius: 7,
            border: "none",
            fontWeight: executiveMode === "report" ? 600 : 500,
            background: executiveMode === "report" ? "#1a232b" : "transparent",
            color: executiveMode === "report" ? "#ffffff" : "#64748b",
            cursor: "pointer",
            transition: "all 0.12s ease",
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
            borderRadius: 7,
            border: "none",
            fontWeight: executiveMode === "research" ? 600 : 500,
            background: executiveMode === "research" ? "#1a232b" : "transparent",
            color: executiveMode === "research" ? "#ffffff" : "#64748b",
            cursor: "pointer",
            transition: "all 0.12s ease",
          }}
        >
          <Search size={13} />
          <span>Research</span>
        </button>
      </div>

      {/* ── Right: Real Model Selector & Actions ─── */}
      <div className="topbar-v6__actions">
        {/* Real Model Selector V7 */}
        <ModelSelectorV7
          models={models}
          providers={providers}
          selectedModelId={selectedModelId}
          isAutoRouter={isAuto}
          onSelectAuto={() => {
            setIsAuto(true);
            onSelectModel?.("auto", "auto");
          }}
          onSelectModel={(model) => {
            setIsAuto(false);
            onSelectModel?.(model.id, model.provider);
          }}
          backendConnected={runtime.backendConnected}
        />

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
