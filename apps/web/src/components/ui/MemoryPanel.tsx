/**
 * MemoryPanel — view, search, and manage HINAA's memories.
 * Categories: facts, preferences, workflows, tasks, conversations.
 */

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain, Search, Trash2, Edit3, Check, X, Tag,
  Star, Bookmark, Clock, MessageSquare,
} from "lucide-react";
import type { IconComponent } from "../../shared/iconType";
import useMemory, { type MemoryEntry } from "../../features/memory/useMemory";

const CATEGORY_CONFIG: Record<MemoryEntry["category"], { icon: IconComponent; color: string; label: string }> = {
  fact: { icon: Star, color: "#f59e0b", label: "Facts" },
  preference: { icon: Bookmark, color: "#ec4899", label: "Preferences" },
  workflow: { icon: Tag, color: "#8b5cf6", label: "Workflows" },
  task: { icon: Clock, color: "#3b82f6", label: "Tasks" },
  conversation: { icon: MessageSquare, color: "#10b981", label: "Conversations" },
};

interface MemoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MemoryPanel({ isOpen, onClose }: MemoryPanelProps) {
  const { entries, removeMemory, updateMemory, searchMemory } = useMemory();
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return entries;
    return searchMemory(search);
  }, [entries, search, searchMemory]);

  const startEdit = (entry: MemoryEntry) => {
    setEditingId(entry.id);
    setEditText(entry.content);
  };

  const saveEdit = () => {
    if (editingId && editText.trim()) {
      updateMemory(editingId, editText.trim());
    }
    setEditingId(null);
    setEditText("");
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: 320, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 320, opacity: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 0.61, 0.36, 1] }}
          style={{
            position: "absolute",
            right: 0,
            top: 0,
            bottom: 0,
            width: 380,
            background: "rgba(255,255,255,0.92)",
            backdropFilter: "blur(28px)",
            WebkitBackdropFilter: "blur(28px)",
            borderLeft: "1px solid rgba(255,255,255,0.8)",
            boxShadow: "-8px 0 40px rgba(0,0,0,0.06)",
            zIndex: 40,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Header */}
          <div style={{ padding: "16px 20px", borderBottom: "1px solid rgba(0,0,0,0.06)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Brain size={20} color="#ec4899" />
              <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>HINAA Memory</span>
            </div>
            <motion.button
              onClick={onClose}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              style={{ width: 32, height: 32, borderRadius: 8, border: "none", background: "rgba(0,0,0,0.04)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <X size={14} />
            </motion.button>
          </div>

          {/* Search */}
          <div style={{ padding: "12px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, background: "rgba(0,0,0,0.03)", borderRadius: 10, padding: "8px 14px" }}>
              <Search size={14} color="#94a3b8" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search memories..."
                style={{ border: "none", outline: "none", background: "transparent", flex: 1, fontSize: "0.82rem", color: "#1a1f2e", fontFamily: "inherit" }}
              />
            </div>
          </div>

          {/* Entries */}
          <div style={{ flex: 1, overflowY: "auto", padding: "0 16px 16px" }}>
            {filtered.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: "#94a3b8", fontSize: "0.85rem" }}>
                {entries.length === 0 ? "No memories yet. HINAA remembers facts and preferences from conversations." : "No matching memories."}
              </div>
            ) : (
              filtered.map((entry) => {
                const config = CATEGORY_CONFIG[entry.category];
                const Icon = config.icon;
                return (
                  <motion.div
                    key={entry.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      background: "rgba(255,255,255,0.7)",
                      borderRadius: 12,
                      border: "1px solid rgba(0,0,0,0.06)",
                      padding: 12,
                      marginBottom: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
                      <Icon size={13} color={config.color} style={{ marginTop: 2, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        {editingId === entry.id ? (
                          <textarea
                            value={editText}
                            onChange={(e) => setEditText(e.target.value)}
                            style={{
                              width: "100%",
                              border: "1px solid rgba(8,145,178,0.3)",
                              borderRadius: 6,
                              padding: 6,
                              fontSize: "0.82rem",
                              fontFamily: "inherit",
                              resize: "vertical",
                              minHeight: 40,
                            }}
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveEdit(); }
                              if (e.key === "Escape") setEditingId(null);
                            }}
                          />
                        ) : (
                          <div style={{ fontSize: "0.82rem", color: "#1a1f2e", lineHeight: 1.5 }}>
                            {entry.content}
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: "0.65rem", color: config.color, fontWeight: 600, textTransform: "uppercase" }}>
                        {config.label}
                      </span>
                      <div style={{ display: "flex", gap: 4 }}>
                        <motion.button
                          onClick={() => editingId === entry.id ? saveEdit() : startEdit(entry)}
                          whileHover={{ scale: 1.1 }}
                          style={{ width: 24, height: 24, borderRadius: 6, border: "none", background: "transparent", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                        >
                          {editingId === entry.id ? <Check size={12} color="#10b981" /> : <Edit3 size={12} color="#94a3b8" />}
                        </motion.button>
                        <motion.button
                          onClick={() => removeMemory(entry.id)}
                          whileHover={{ scale: 1.1 }}
                          style={{ width: 24, height: 24, borderRadius: 6, border: "none", background: "transparent", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                        >
                          <Trash2 size={12} color="#ef4444" />
                        </motion.button>
                      </div>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default MemoryPanel;
