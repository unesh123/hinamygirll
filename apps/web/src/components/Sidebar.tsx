import React from "react";
import {
  MessageSquare,
  Sparkles,
  Layers,
  Terminal,
  Cpu,
  Settings,
  Plus,
  Compass,
} from "lucide-react";

export interface ConversationSummary {
  id: string;
  title: string;
  timestamp: string;
  isActive?: boolean;
}

export interface SidebarProps {
  conversations?: ConversationSummary[];
  activeConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onNewChat?: () => void;
  onOpenTerminal?: () => void;
  onOpenModels?: () => void;
  onOpenSettings?: () => void;
}

export function Sidebar({
  conversations = [
    { id: "default", title: "Main Engineering Session", timestamp: "Just now", isActive: true },
    { id: "agentic-audit", title: "Phase 04 Identity & Mood", timestamp: "10m ago" },
    { id: "telemetry-lab", title: "Performance Trace P95", timestamp: "1h ago" },
  ],
  activeConversationId = "default",
  onSelectConversation,
  onNewChat,
  onOpenTerminal,
  onOpenModels,
  onOpenSettings,
}: SidebarProps) {
  return (
    <aside className="w-[260px] h-full flex flex-col min-w-0 min-h-0 bg-frost/70 backdrop-blur-md border border-glass-border rounded-xl shadow-soft p-3">
      {/* ── New Chat Action ── */}
      <button
        type="button"
        onClick={onNewChat}
        className="w-full flex items-center justify-center gap-2 py-2 px-3 mb-3 bg-gradient-to-r from-accent to-brand-300 hover:opacity-95 text-white font-medium text-xs rounded-lg shadow-xs transition-transform active:scale-[0.98] flex-shrink-0"
      >
        <Plus size={14} />
        <span>New Session</span>
      </button>

      {/* ── Section Title ── */}
      <div className="flex items-center justify-between px-1 mb-2 flex-shrink-0">
        <span className="text-[10px] font-bold tracking-wider text-text-muted uppercase">
          Conversations
        </span>
        <Compass size={12} className="text-text-muted" />
      </div>

      {/* ── Conversation List (overflow-y-auto min-h-0) ── */}
      <div className="flex-1 overflow-y-auto min-h-0 flex flex-col gap-1 pr-1">
        {conversations.map((c) => {
          const isActive = c.id === activeConversationId || c.isActive;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => onSelectConversation?.(c.id)}
              className={`w-full text-left p-2 rounded-lg transition-colors flex items-start gap-2.5 min-w-0 ${
                isActive
                  ? "bg-brand-100/60 text-accent font-medium border border-brand-300/30"
                  : "hover:bg-frost-light text-text-secondary"
              }`}
            >
              <MessageSquare size={13} className="mt-0.5 flex-shrink-0 text-text-muted" />
              <div className="flex-1 min-w-0 truncate">
                <p className="text-xs truncate">{c.title}</p>
                <span className="text-[10px] text-text-muted">{c.timestamp}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* ── Bottom Actions (flex-shrink-0) ── */}
      <div className="border-t border-glass-border pt-2 mt-2 flex flex-col gap-1 flex-shrink-0">
        {onOpenTerminal && (
          <button
            type="button"
            onClick={onOpenTerminal}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-frost-light text-xs text-text-secondary transition-colors"
          >
            <Terminal size={13} className="text-text-muted" />
            <span>Terminal Sandbox</span>
          </button>
        )}
        {onOpenModels && (
          <button
            type="button"
            onClick={onOpenModels}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-frost-light text-xs text-text-secondary transition-colors"
          >
            <Cpu size={13} className="text-text-muted" />
            <span>Neural Registry</span>
          </button>
        )}
        {onOpenSettings && (
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-frost-light text-xs text-text-secondary transition-colors"
          >
            <Settings size={13} className="text-text-muted" />
            <span>System Settings</span>
          </button>
        )}
      </div>
    </aside>
  );
}
