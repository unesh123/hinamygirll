/**
 * SidebarPanel — expandable sidebar with working content panels.
 * Each nav section has its own panel: Chat, Voice, Tasks, Files, Memory, Tools.
 */

import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare, X, Plus, File,
} from "lucide-react";
import type { NavSection } from "./NavRail";

interface SidebarPanelProps {
  section: NavSection | null;
  onClose: () => void;
  onNewChat?: () => void;
}

/* ─── Section content renderers ────────────────────────── */
function ConversationsPanel() {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        Recent Conversations
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {["Current session", "Previous chat"].map((name, i) => (
          <div
            key={i}
            style={{
              padding: "10px 12px",
              borderRadius: 10,
              background: i === 0 ? "rgba(167,243,208,0.15)" : "rgba(255,255,255,0.5)",
              border: "1px solid rgba(0,0,0,0.05)",
              cursor: "pointer",
              fontSize: "0.82rem",
              color: "#1a1f2e",
              fontWeight: i === 0 ? 600 : 400,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <MessageSquare size={13} color={i === 0 ? "#059669" : "#94a3b8"} />
              <span>{name}</span>
            </div>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", marginTop: 3 }}>
              {i === 0 ? "Active now" : "2 days ago"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VoicePanel() {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        Voice Settings
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ padding: 12, borderRadius: 10, background: "rgba(255,255,255,0.6)", border: "1px solid rgba(0,0,0,0.05)", fontSize: "0.82rem", color: "#475569" }}>
          <div style={{ fontWeight: 600, marginBottom: 4, color: "#1a1f2e" }}>🎤 Microphone</div>
          Click the mic button or say "Hey HINAA" to start voice conversation.
        </div>
        <div style={{ padding: 12, borderRadius: 10, background: "rgba(255,255,255,0.6)", border: "1px solid rgba(0,0,0,0.05)", fontSize: "0.82rem", color: "#475569" }}>
          <div style={{ fontWeight: 600, marginBottom: 4, color: "#1a1f2e" }}>🔊 Speaker</div>
          HINAA speaks back using text-to-speech. Headphones recommended for best experience.
        </div>
        <div style={{ padding: 12, borderRadius: 10, background: "rgba(255,255,255,0.6)", border: "1px solid rgba(0,0,0,0.05)", fontSize: "0.82rem", color: "#475569" }}>
          <div style={{ fontWeight: 600, marginBottom: 4, color: "#1a1f2e" }}>🌐 Languages</div>
          HINAA understands Hindi, English, and code-switching naturally.
        </div>
      </div>
    </div>
  );
}

function TasksPanel() {
  const tasks = [
    { title: "Welcome to HINAA", done: true },
    { title: "Try voice conversation", done: false },
    { title: "Use @ power-ups", done: false },
    { title: "Explore tools & automation", done: false },
  ];

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span>Active Tasks</span>
        <Plus size={14} color="#94a3b8" />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {tasks.map((t, i) => (
          <div
            key={i}
            style={{
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(255,255,255,0.6)",
              border: "1px solid rgba(0,0,0,0.05)",
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontSize: "0.82rem",
              color: t.done ? "#94a3b8" : "#1a1f2e",
              textDecoration: t.done ? "line-through" : "none",
            }}
          >
            <div style={{
              width: 18, height: 18, borderRadius: "50%",
              border: `2px solid ${t.done ? "#10b981" : "#cbd5e1"}`,
              background: t.done ? "#10b981" : "transparent",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0,
            }}>
              {t.done && <span style={{ color: "white", fontSize: 10 }}>✓</span>}
            </div>
            {t.title}
          </div>
        ))}
      </div>
    </div>
  );
}

function FilesPanel() {
  const files = [
    { name: "README.md", type: "doc", date: "2 days ago" },
    { name: "project-plan.md", type: "doc", date: "5 days ago" },
  ];

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        Recent Files
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {files.map((f, i) => (
          <div
            key={i}
            style={{
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(255,255,255,0.6)",
              border: "1px solid rgba(0,0,0,0.05)",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <File size={14} color="#64748b" />
              <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#1a1f2e" }}>{f.name}</span>
            </div>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", marginTop: 3, marginLeft: 22 }}>{f.date}</div>
          </div>
        ))}
        {files.length === 0 && (
          <div style={{ textAlign: "center", padding: 20, color: "#94a3b8", fontSize: "0.82rem" }}>
            No files yet. Create or share files with HINAA.
          </div>
        )}
      </div>
    </div>
  );
}

function MemoryPanelView() {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        What HINAA Remembers
      </div>
      <div style={{ padding: 12, borderRadius: 10, background: "rgba(255,255,255,0.6)", border: "1px solid rgba(0,0,0,0.05)", fontSize: "0.82rem", color: "#475569", lineHeight: 1.6 }}>
        <strong style={{ color: "#1a1f2e" }}>Memory stores:</strong>
        <ul style={{ marginTop: 8, paddingLeft: 16 }}>
          <li>Facts you share</li>
          <li>Your preferences</li>
          <li>Workflow patterns</li>
          <li>Active tasks & goals</li>
          <li>Conversation context</li>
        </ul>
        <div style={{ marginTop: 12, fontStyle: "italic", fontSize: "0.75rem" }}>
          Say "remember this" to save or "forget that" to remove.
        </div>
      </div>
    </div>
  );
}

function ToolsPanelView() {
  const tools = [
    { name: "Web Search", status: "connected" },
    { name: "Browser", status: "connected" },
    { name: "Image Search", status: "connected" },
    { name: "Image Generation", status: "needs-setup" },
    { name: "Email", status: "needs-auth" },
    { name: "Calendar", status: "needs-auth" },
    { name: "Code Tools", status: "connected" },
    { name: "File System", status: "connected" },
  ];

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        Connected Tools
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {tools.map((t, i) => (
          <div
            key={i}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              background: "rgba(255,255,255,0.5)",
              border: "1px solid rgba(0,0,0,0.05)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "0.8rem",
            }}
          >
            <span style={{ color: "#1a1f2e" }}>{t.name}</span>
            <span style={{
              fontSize: "0.6rem",
              fontWeight: 600,
              padding: "3px 8px",
              borderRadius: 6,
              background: t.status === "connected" ? "rgba(16,185,129,0.12)" : t.status === "needs-auth" ? "rgba(245,158,11,0.12)" : "rgba(148,163,184,0.12)",
              color: t.status === "connected" ? "#059669" : t.status === "needs-auth" ? "#d97706" : "#64748b",
            }}>
              {t.status === "connected" ? "Ready" : t.status === "needs-auth" ? "Auth needed" : "Setup needed"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Main Component ───────────────────────────────────── */
export function SidebarPanel({ section, onClose }: SidebarPanelProps) {
  if (!section) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="sidebar-panel"
        initial={{ x: -320, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: -320, opacity: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 0.61, 0.36, 1] }}
        style={{
          position: "absolute",
          left: 60,
          top: 0,
          bottom: 0,
          width: 300,
          background: "rgba(255,255,255,0.9)",
          backdropFilter: "blur(28px)",
          WebkitBackdropFilter: "blur(28px)",
          borderRight: "1px solid rgba(255,255,255,0.8)",
          boxShadow: "4px 0 40px rgba(0,0,0,0.06)",
          zIndex: 30,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div style={{
          padding: "14px 16px",
          borderBottom: "1px solid rgba(0,0,0,0.05)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}>
          <span style={{ fontWeight: 700, fontSize: "0.88rem", textTransform: "capitalize" }}>
            {section}
          </span>
          <motion.button
            onClick={onClose}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            style={{
              width: 28, height: 28, borderRadius: 8,
              border: "none", background: "rgba(0,0,0,0.04)",
              cursor: "pointer", display: "flex",
              alignItems: "center", justifyContent: "center",
            }}
          >
            <X size={13} />
          </motion.button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {section === "chat" && <ConversationsPanel />}
          {section === "voice" && <VoicePanel />}
          {section === "tasks" && <TasksPanel />}
          {section === "files" && <FilesPanel />}
          {section === "memory" && <MemoryPanelView />}
          {section === "tools" && <ToolsPanelView />}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export default SidebarPanel;
