import React from "react";
import {
  MessageSquare,
  LayoutGrid,
  Cpu,
  FileText,
  Settings,
  Plus,
  Sparkles,
  User,
  Circle,
  History,
  Mic,
} from "lucide-react";
import { useCapabilities } from "../../features/providers/hooks/useCapabilities";

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
  | "settings"
  | "dashboard"
  | "models"
  | "reports";

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
  isOnline = false,
  isDark = false,
  onToggleTheme,
}: NavigationRailProps) {
  const isChatActive = active === "chat";
  const isTalkActive = active === "talk" || active === "voice";
  const { capabilities, loading: capsLoading, error: capsError } = useCapabilities();
  const { runtime, features, providers } = capabilities;
  const configuredProviders = providers.filter((p) => p.configured).length;
  const backendOk = runtime.backendConnected && !capsError && isOnline;

  // Never assert health the rail has not measured — these literals stayed green
  // through a total backend outage.
  const status = capsLoading
    ? { dot: "#94a3b8", headline: "Checking systems…", detail: "Probing /v1/capabilities" }
    : backendOk
      ? {
          dot: "#10b981",
          headline: "All systems nominal",
          detail: `${configuredProviders} providers · ${runtime.activeMode} mode`,
        }
      : {
          dot: "#ef4444",
          headline: "Backend unreachable",
          detail: capsError ? capsError : "API not responding",
        };

  const ownerName = runtime.ownerName.trim();
  const ownerInitials = ownerName
    ? ownerName
        .split(/\s+/)
        .slice(0, 2)
        .map((word) => word[0]?.toUpperCase() ?? "")
        .join("")
    : "··";
  const sessionLine = capsLoading
    ? "Identifying session…"
    : capsError
      ? "Session unknown"
      : `${runtime.environment} · ${runtime.authMode} auth`;

  const sources = [
    { label: "Knowledge Base", color: "#10b981", ready: features.memory },
    { label: "Web Search", color: "#3b82f6", ready: features.webSearch },
    { label: "Artifacts", color: "#f59e0b", ready: features.artifacts },
  ];

  const navItems = [
    {
      id: "talk" as NavSection,
      title: "Talk",
      subtitle: "Voice and avatar",
      icon: Mic,
      active: isTalkActive,
    },
    {
      id: "chat" as NavSection,
      title: "Chat",
      subtitle: "Converse with HINA",
      icon: MessageSquare,
      active: isChatActive,
    },
    {
      id: "dashboard" as NavSection,
      title: "Dashboard",
      subtitle: "System overview",
      icon: LayoutGrid,
      active: active === "dashboard" || active === "tasks",
    },
    {
      id: "models" as NavSection,
      title: "Models",
      subtitle: "AI model selection",
      icon: Cpu,
      active: active === "models" || active === "creations",
    },
    {
      id: "reports" as NavSection,
      title: "Reports",
      subtitle: "Generated documents",
      icon: FileText,
      active: active === "reports" || active === "files" || active === "library",
    },
    {
      id: "settings" as NavSection,
      title: "Settings",
      subtitle: "Preferences",
      icon: Settings,
      active: active === "settings",
    },
  ];

  return (
    <aside
      className="sakura-nav-rail"
      data-testid="executive-nav-sidebar"
      aria-label="HINAA navigation"
      style={{
        width: 260,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#ffffff",
        borderRight: "1px solid #e2e8f0",
        padding: "16px 14px",
        flexShrink: 0,
        zIndex: 30,
        userSelect: "none",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
      }}
    >
      {/* ── Brand / Header ──────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 6px 16px 6px" }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 10,
            background: "#1a232b",
            color: "#ffffff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 2px 6px rgba(26, 35, 43, 0.2)",
          }}
        >
          <Sparkles size={16} />
        </div>
        <div>
          <div
            style={{
              fontWeight: 800,
              fontSize: 14,
              letterSpacing: "0.14em",
              color: "#0f172a",
              lineHeight: 1.1,
            }}
          >
            H I N A
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", fontWeight: 500, letterSpacing: "0.02em" }}>
            Intelligence OS
          </div>
        </div>
      </div>

      {/* ── Profile Card ────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "8px 10px",
          background: "#ffffff",
          borderRadius: 12,
          border: "1px solid #f1f5f9",
          boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
          marginBottom: 12,
        }}
      >
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
            fontWeight: 700,
            fontSize: 11,
            flexShrink: 0,
          }}
        >
          {ownerInitials}
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "#1e293b",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {ownerName || "Not reported"}
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", fontWeight: 500 }}>
            {sessionLine}
          </div>
        </div>
      </div>

      {/* ── Measured exposure state ─────────────────── */}
      {!capsLoading && !capsError && runtime.privateDataOpen && (
        <div
          style={{
            fontSize: 10,
            lineHeight: 1.45,
            fontWeight: 500,
            color: "#92400e",
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 10,
            padding: "7px 9px",
            marginBottom: 12,
          }}
        >
          Anyone with this URL can read memories, chats and tasks. Set{' '}
          <code style={{ fontFamily: "inherit", fontWeight: 700 }}>HINAA_AUTH_MODE=clerk</code>{' '}
          and a token-verified owner.
        </div>
      )}

      {/* ── Primary Action: + New Session ──────────── */}
      {onNewChat && (
        <button
          type="button"
          data-testid="new-session-sidebar-btn"
          onClick={onNewChat}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "9px 12px",
            background: "#1a232b",
            color: "#ffffff",
            borderRadius: 12,
            border: "none",
            cursor: "pointer",
            marginBottom: 14,
            boxShadow: "0 2px 4px rgba(26, 35, 43, 0.15)",
            transition: "all 0.15s ease",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 600 }}>
            <Plus size={15} />
            <span>New Session</span>
          </div>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              padding: "1px 6px",
              borderRadius: 5,
              background: "rgba(255, 255, 255, 0.15)",
              color: "rgba(255, 255, 255, 0.8)",
            }}
          >
            ⌘N
          </span>
        </button>
      )}

      {/* ── Conversation History: opens the saved-thread panel ── */}
      {onToggleHistory && (
        <button
          type="button"
          data-testid="history-sidebar-btn"
          aria-pressed={historyOpen}
          onClick={onToggleHistory}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            width: "100%",
            padding: "8px 12px",
            marginBottom: 14,
            fontSize: 12,
            fontWeight: 600,
            color: historyOpen ? "#ffffff" : "#475569",
            background: historyOpen ? "#1a232b" : "#ffffff",
            border: `1px solid ${historyOpen ? "#1a232b" : "#e2e8f0"}`,
            borderRadius: 12,
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          <History size={15} />
          <span>History</span>
        </button>
      )}

      {/* ── Nav Tabs List ───────────────────────────── */}
      <nav style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.active;

          return (
            <button
              key={item.id}
              type="button"
              data-testid={`sidebar-nav-${item.id}`}
              aria-label={item.title}
              onClick={() => onNavigate(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                borderRadius: 10,
                border: isActive ? "1px solid rgba(226, 232, 240, 0.8)" : "1px solid transparent",
                background: isActive ? "#f1f5f9" : "transparent",
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.12s ease",
                position: "relative",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Icon
                  size={16}
                  style={{
                    color: isActive ? "#0f172a" : "#64748b",
                    flexShrink: 0,
                  }}
                />
                <div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: isActive ? 650 : 500,
                      color: isActive ? "#0f172a" : "#475569",
                      lineHeight: 1.2,
                    }}
                  >
                    {item.title}
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: "#94a3b8",
                      lineHeight: 1.2,
                      marginTop: 1,
                    }}
                  >
                    {item.subtitle}
                  </div>
                </div>
              </div>

              {isActive && (
                <div
                  style={{
                    width: 3,
                    height: 18,
                    borderRadius: 9999,
                    background: "#f43f5e",
                  }}
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* ── CONNECTED SOURCES Section ──────────────── */}
      <div style={{ marginTop: 20 }}>
        <div
          style={{
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: "0.08em",
            color: "#94a3b8",
            textTransform: "uppercase",
            padding: "4px 8px 8px 8px",
          }}
        >
          CONNECTED SOURCES
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "0 8px" }}>
          {sources.map((src) => (
            <div
              key={src.label}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "#475569" }}>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: capsLoading ? "#cbd5e1" : src.ready ? src.color : "#cbd5e1",
                    flexShrink: 0,
                  }}
                />
                <span>{src.label}</span>
              </div>
              <span
                style={{
                  fontSize: 10,
                  color: !capsLoading && src.ready ? "#10b981" : "#94a3b8",
                  fontWeight: 500,
                }}
              >
                {capsLoading ? "Checking" : src.ready ? "Available" : "Unavailable"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Footer ─────────────────────────────────── */}
      <div style={{ marginTop: "auto", paddingTop: 16, borderTop: "1px solid #f1f5f9" }}>
        {!capsLoading && !backendOk && (
          <div
            data-testid="rail-degraded-banner"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              marginBottom: 8,
              padding: "6px 8px",
              borderRadius: 8,
              background: "#fef2f2",
              border: "1px solid #fecaca",
              fontSize: 10,
              lineHeight: 1.4,
              color: "#991b1b",
            }}
          >
            <Circle size={8} fill="#ef4444" stroke="#ef4444" style={{ flexShrink: 0 }} />
            <span>Degraded — HINAA cannot reach its backend, so chat replies will fail.</span>
          </div>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2, paddingLeft: 4 }}>
          <span
            data-testid="rail-status-dot"
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: status.dot,
            }}
          />
          <span style={{ fontSize: 11, fontWeight: 600, color: "#1e293b" }}>
            {status.headline}
          </span>
        </div>
        <div style={{ fontSize: 10, color: "#94a3b8", paddingLeft: 19 }}>{status.detail}</div>

        <button
          type="button"
          onClick={() => onNavigate("settings")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginTop: 12,
            padding: "6px 8px",
            borderRadius: 8,
            border: "none",
            background: "transparent",
            color: "#64748b",
            fontSize: 11,
            cursor: "pointer",
            width: "100%",
            textAlign: "left",
          }}
        >
          <User size={13} />
          <span>Account</span>
        </button>
      </div>

      <style>{`
        .sakura-nav-rail {
          display: flex;
        }
        @media (max-width: 768px) {
          .sakura-nav-rail {
            display: none !important;
          }
        }
      `}</style>
    </aside>
  );
}
