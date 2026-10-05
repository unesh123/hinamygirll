import { UserButton } from "@clerk/react";
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
  Plus,
} from "lucide-react";
import { ModelSelectorV7 } from "../chat/ModelSelectorV7";
import { useCapabilities } from "../../features/providers/hooks/useCapabilities";
import { DynamicIslandCompanion, type DynamicIslandCompanionProps } from "./DynamicIslandCompanion";

export type WorkspaceMode = "talk" | "work" | "operate" | "showroom" | "vault" | "models";
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
  selectedProviderId?: string | null;
  isAutoRouter?: boolean;
  executiveMode: ExecutiveMode;
  onExecutiveModeChange: (mode: ExecutiveMode) => void;
  onNewChat?: () => void;
  islandProps?: DynamicIslandCompanionProps;
}

export const TopBarV6: React.FC<TopBarV6Props> = ({
  currentMode,
  onModeChange,
  activeProject = { id: "default", name: "HINA Workspace", repo: "main" },
  isDark = true,
  onToggleTheme,
  onOpenSearch,
  onSelectModel,
  selectedModelId,
  selectedProviderId,
  isAutoRouter,
  executiveMode,
  onExecutiveModeChange,
  onNewChat,
  islandProps,
}) => {
  const { models, providers, runtime, loading, refetch } = useCapabilities();
  const isAuto = isAutoRouter ?? !selectedModelId;

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
        background: isDark ? "rgba(9, 10, 15, 0.98)" : "#ffffff",
        borderBottom: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid #e2e8f0",
        zIndex: 2500,
        userSelect: "none",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif",
        padding: "0 14px",
        height: 52,
        position: "relative",
      }}
    >
      {/* ── Left: Breadcrumb & Executive Workspace Modes ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {/* Breadcrumb */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button
            type="button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: "transparent",
              border: "none",
              color: isDark ? "#94a3b8" : "#64748b",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              padding: 0,
            }}
          >
            <span>HINA STUDIO</span>
            <ChevronDown size={11} style={{ opacity: 0.7 }} />
          </button>
          <span style={{ color: isDark ? "rgba(255, 255, 255, 0.2)" : "#cbd5e1", fontSize: 12 }}>/</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: isDark ? "#ffffff" : "#0f172a" }}>
            {{
              chat: "Chat",
              work: "Chat",
              talk: "Talk",
              showroom: "Runway 3D",
              operate: "Dashboard",
              dashboard: "Dashboard",
              models: "Models",
              reports: "Reports",
              vault: "VIP Vault",
              settings: "Settings",
            }[currentMode] || "Chat"}
          </span>
        </div>

        {/* Executive Mode Tabs (Adobe Premiere / AE Workspace Tab Style) */}
        <div
          className="topbar-v6__modes"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 2,
            background: isDark ? "rgba(255, 255, 255, 0.05)" : "#f1f5f9",
            padding: "2px 3px",
            borderRadius: 8,
            border: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid #e2e8f0",
          }}
        >
          <button
            type="button"
            data-testid="mode-chat"
            onClick={() => handleModeClick("chat")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              borderRadius: 6,
              border: "none",
              padding: "4px 8px",
              fontSize: 11,
              fontWeight: executiveMode === "chat" ? 700 : 500,
              background: executiveMode === "chat" ? (isDark ? "rgba(255,255,255,0.14)" : "#ffffff") : "transparent",
              color: executiveMode === "chat" ? (isDark ? "#ffffff" : "#0f172a") : (isDark ? "#94a3b8" : "#64748b"),
              cursor: "pointer",
              boxShadow: executiveMode === "chat" ? (isDark ? "0 1px 4px rgba(0,0,0,0.4)" : "0 1px 2px rgba(0,0,0,0.08)") : "none",
            }}
          >
            <MessageSquare size={12} color={executiveMode === "chat" ? "#00d4ff" : undefined} />
            <span>Chat</span>
          </button>

          <button
            type="button"
            data-testid="mode-deep-reasoning"
            onClick={() => handleModeClick("deep-reasoning")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              borderRadius: 6,
              border: "none",
              padding: "4px 8px",
              fontSize: 11,
              fontWeight: executiveMode === "deep-reasoning" ? 700 : 500,
              background: executiveMode === "deep-reasoning" ? (isDark ? "rgba(255,255,255,0.14)" : "#ffffff") : "transparent",
              color: executiveMode === "deep-reasoning" ? (isDark ? "#ffffff" : "#0f172a") : (isDark ? "#94a3b8" : "#64748b"),
              cursor: "pointer",
              boxShadow: executiveMode === "deep-reasoning" ? (isDark ? "0 1px 4px rgba(0,0,0,0.4)" : "0 1px 2px rgba(0,0,0,0.08)") : "none",
            }}
          >
            <Brain size={12} color={executiveMode === "deep-reasoning" ? "#ec4899" : undefined} />
            <span>Deep Reasoning</span>
          </button>

          <button
            type="button"
            data-testid="mode-report"
            onClick={() => handleModeClick("report")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              borderRadius: 6,
              border: "none",
              padding: "4px 8px",
              fontSize: 11,
              fontWeight: executiveMode === "report" ? 700 : 500,
              background: executiveMode === "report" ? (isDark ? "rgba(255,255,255,0.14)" : "#ffffff") : "transparent",
              color: executiveMode === "report" ? (isDark ? "#ffffff" : "#0f172a") : (isDark ? "#94a3b8" : "#64748b"),
              cursor: "pointer",
              boxShadow: executiveMode === "report" ? (isDark ? "0 1px 4px rgba(0,0,0,0.4)" : "0 1px 2px rgba(0,0,0,0.08)") : "none",
            }}
          >
            <FileText size={12} color={executiveMode === "report" ? "#f59e0b" : undefined} />
            <span>Report</span>
          </button>

          <button
            type="button"
            data-testid="mode-research"
            onClick={() => handleModeClick("research")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              borderRadius: 6,
              border: "none",
              padding: "4px 8px",
              fontSize: 11,
              fontWeight: executiveMode === "research" ? 700 : 500,
              background: executiveMode === "research" ? (isDark ? "rgba(255,255,255,0.14)" : "#ffffff") : "transparent",
              color: executiveMode === "research" ? (isDark ? "#ffffff" : "#0f172a") : (isDark ? "#94a3b8" : "#64748b"),
              cursor: "pointer",
              boxShadow: executiveMode === "research" ? (isDark ? "0 1px 4px rgba(0,0,0,0.4)" : "0 1px 2px rgba(0,0,0,0.08)") : "none",
            }}
          >
            <Search size={12} color={executiveMode === "research" ? "#10b981" : undefined} />
            <span>Research</span>
          </button>
        </div>
      </div>

      {/* ── Center: INA ISLAND APEX CORE ─────────────────── */}
      {islandProps && (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            transform: "translate(-50%, -50%)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            pointerEvents: "auto",
            zIndex: 10,
          }}
        >
          <DynamicIslandCompanion
            {...islandProps}
            inlineInTopBar={true}
            isDark={isDark}
            availableModels={models}
            onSelectModel={onSelectModel}
          />
        </div>
      )}

      {/* ── Right: Real Model Selector & Executive Actions ── */}
      <div className="topbar-v6__actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {/* Real Model Selector V7 */}
        <ModelSelectorV7
          models={models}
          providers={providers}
          selectedModelId={selectedModelId}
          selectedProviderId={selectedProviderId}
          isAutoRouter={isAuto}
          onSelectAuto={() => onSelectModel?.("auto", "auto")}
          onSelectModel={(model) => onSelectModel?.(model.id, model.provider)}
          backendConnected={runtime.backendConnected}
          isDark={isDark}
        />

        {/* + New Chat Session */}
        {onNewChat && (
          <button
            type="button"
            data-testid="topbar-new-chat-btn"
            onClick={onNewChat}
            title="Start new conversation (⌘N / Ctrl+N)"
            style={{
              height: 32,
              padding: "0 10px",
              borderRadius: 8,
              border: isDark ? "1px solid rgba(255, 255, 255, 0.14)" : "1px solid #cbd5e1",
              background: isDark ? "rgba(255, 255, 255, 0.08)" : "#f8fafc",
              color: isDark ? "#ffffff" : "#0f172a",
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 12,
              fontWeight: 650,
              cursor: "pointer",
              transition: "all 0.12s ease",
            }}
          >
            <Plus size={13} strokeWidth={2.5} />
            <span>New Chat</span>
          </button>
        )}

        {/* Runway 3D Showroom */}
        <button
          type="button"
          data-testid="topbar-showroom-btn"
          onClick={() => onModeChange(currentMode === "showroom" ? "work" : "showroom")}
          title="DICH Haute-Couture 3D Runway Showroom"
          style={{
            height: 32,
            padding: "0 12px",
            borderRadius: 9999,
            border: currentMode === "showroom"
              ? "1.5px solid #00d4ff"
              : isDark
              ? "1px solid rgba(255, 255, 255, 0.12)"
              : "1px solid #e2e8f0",
            background: currentMode === "showroom"
              ? "rgba(0, 212, 255, 0.15)"
              : isDark
              ? "rgba(255, 255, 255, 0.06)"
              : "#ffffff",
            color: currentMode === "showroom" ? "#00d4ff" : isDark ? "#ffffff" : "#475569",
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: currentMode === "showroom" ? "0 0 12px rgba(0, 212, 255, 0.3)" : "none",
            transition: "all 0.12s ease",
          }}
        >
          <Sparkles size={13} color={currentMode === "showroom" ? "#00d4ff" : "#ec4899"} />
          <span>Runway 3D</span>
        </button>

        <button type="button" className="workspace-connection" onClick={() => void refetch()}
          title="Refresh workspace connection" aria-label={`Workspace ${runtime.backendConnected ? "connected" : loading ? "connecting" : "offline"}. Refresh connection.`}
          style={{ display:"flex", alignItems:"center", gap:5, border:"1px solid currentColor", borderRadius:20, padding:"5px 8px", background:"transparent", fontSize:10, color:runtime.backendConnected ? "#87cba9" : "#d6ab87", cursor:"pointer" }}>
          <span style={{ width:5, height:5, background:"currentColor", borderRadius:"50%" }} />
          <span>{runtime.backendConnected ? "Connected" : loading ? "Connecting" : "Offline"}</span>
        </button>
        {/* Search */}
        <button
          type="button"
          onClick={onOpenSearch}
          title="Search (⌘K)"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            border: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid #e2e8f0",
            background: isDark ? "rgba(255, 255, 255, 0.06)" : "#ffffff",
            color: isDark ? "#cbd5e1" : "#64748b",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <Search size={14} />
        </button>

        {/* Dark/Light Theme */}
        {onToggleTheme && (
          <button
            type="button"
            onClick={onToggleTheme}
            title={isDark ? "Light Mode" : "Dark Mode"}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              border: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid #e2e8f0",
              background: isDark ? "rgba(255, 255, 255, 0.06)" : "#ffffff",
              color: isDark ? "#cbd5e1" : "#64748b",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            {isDark ? <Moon size={14} /> : <Sun size={14} />}
          </button>
        )}

        {/* Account controls use the actual Clerk session in the live workspace. */}
        {import.meta.env.VITE_HINAA_AUTH_MODE === "clerk" ? <UserButton /> : <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 9999,
            background: "linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%)",
            color: "#ffffff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            fontWeight: 800,
            flexShrink: 0,
            boxShadow: "0 0 10px rgba(236,72,153,0.4)",
          }}
        >
          UB
        </div>}
      </div>
    </header>
  );
};
