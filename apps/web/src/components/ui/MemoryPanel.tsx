/**
 * MemoryPanel — view, search, and manage HINAA's durable local memories.
 * Responsive dark-plum Ink Rose aesthetic.
 */

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  Brain, Search, Trash2, Edit3, Check, X, Tag, ShieldAlert,
  Star, Bookmark, Clock, MessageSquare, type LucideIcon,
} from "lucide-react";
import useMemory, { type MemoryEntry } from "../../features/memory/useMemory";

const CATEGORY_CONFIG: Record<string, { icon: LucideIcon; color: string; label: string }> = {
  fact: { icon: Star, color: "#f59e0b", label: "Facts" },
  preference: { icon: Bookmark, color: "#ec4899", label: "Preferences" },
  workflow: { icon: Tag, color: "#8b5cf6", label: "Workflows" },
  task: { icon: Clock, color: "#3b82f6", label: "Tasks" },
  conversation: { icon: MessageSquare, color: "#10b981", label: "Conversations" },
  other: { icon: Bookmark, color: "#a8a29e", label: "Other" },
};

function getCategoryConfig(cat: string) {
  return CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.other;
}

interface MemoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MemoryPanel({ isOpen, onClose }: MemoryPanelProps) {
  const { entries, loading, error, removeMemory, updateMemory, clearAll, searchMemory } =
    useMemory({ enabled: isOpen });
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [editExpiry, setEditExpiry] = useState<number | null>(null); // days
  
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);

  const shouldReduceMotion = useReducedMotion();

  const filtered = useMemo(() => {
    if (!search.trim()) return entries;
    return searchMemory(search);
  }, [entries, search, searchMemory]);

  const startEdit = (entry: MemoryEntry) => {
    setEditingId(entry.id);
    setEditText(entry.content);
    setEditExpiry(null); // Keep until removed by default
  };

  const saveEdit = () => {
    if (editingId && editText.trim()) {
      let expiresAt: string | null = null;
      if (editExpiry !== null) {
        const d = new Date();
        d.setDate(d.getDate() + editExpiry);
        expiresAt = d.toISOString();
      }
      updateMemory(editingId, editText.trim(), expiresAt);
    }
    setEditingId(null);
    setEditText("");
    setEditExpiry(null);
  };

  const handleClearAll = () => {
    clearAll();
    setConfirmClearAll(false);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%", opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: "100%", opacity: 0 }}
          transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.35, ease: [0.22, 0.61, 0.36, 1] }}
          style={{
            position: "absolute",
            right: 0,
            top: 0,
            bottom: 0,
            width: "100%",
            maxWidth: 400,
            background: "rgba(24, 18, 27, 0.95)", // dark plum
            backdropFilter: "blur(28px)",
            WebkitBackdropFilter: "blur(28px)",
            borderLeft: "1px solid rgba(255,255,255,0.1)",
            boxShadow: "-8px 0 40px rgba(0,0,0,0.5)",
            zIndex: 50,
            display: "flex",
            flexDirection: "column",
            color: "#e2d5e5"
          }}
        >
          {/* Header */}
          <div style={{ padding: "20px", borderBottom: "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Brain size={22} color="#ec4899" />
              <div>
                <div style={{ fontWeight: 600, fontSize: "1.05rem", color: "#fdf8ff" }}>Reviewable Memory</div>
                <div style={{ fontSize: "0.75rem", color: "#a89eb0", display: "flex", alignItems: "center", gap: 4 }}>
                  <ShieldAlert size={10} /> Local device only
                </div>
              </div>
            </div>
            <motion.button
              onClick={onClose}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              style={{ width: 32, height: 32, borderRadius: 8, border: "none", background: "rgba(255,255,255,0.08)", color: "#e2d5e5", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <X size={16} />
            </motion.button>
          </div>

          {/* Search & Actions */}
          <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, background: "rgba(255,255,255,0.06)", borderRadius: 10, padding: "10px 14px" }}>
              <Search size={16} color="#94a3b8" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search memories..."
                style={{ border: "none", outline: "none", background: "transparent", flex: 1, fontSize: "0.9rem", color: "#fdf8ff", fontFamily: "inherit" }}
              />
            </div>
            
            {entries.length > 0 && (
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                {!confirmClearAll ? (
                  <button onClick={() => setConfirmClearAll(true)} style={{ background: "transparent", border: "none", color: "#ef4444", fontSize: "0.8rem", cursor: "pointer", opacity: 0.8 }}>Clear all memories</button>
                ) : (
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: "0.75rem", color: "#ef4444" }}>Are you sure?</span>
                    <button onClick={handleClearAll} style={{ background: "#ef4444", color: "#fff", border: "none", borderRadius: 4, padding: "4px 8px", fontSize: "0.75rem", cursor: "pointer" }}>Yes</button>
                    <button onClick={() => setConfirmClearAll(false)} style={{ background: "rgba(255,255,255,0.1)", color: "#fff", border: "none", borderRadius: 4, padding: "4px 8px", fontSize: "0.75rem", cursor: "pointer" }}>No</button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Entries */}
          <div style={{ flex: 1, overflowY: "auto", padding: "0 20px 20px" }}>
            {loading ? (
              <div style={{ textAlign: "center", padding: 40, color: "#a89eb0", fontSize: "0.9rem" }}>Loading memories...</div>
            ) : error && entries.length === 0 ? (
              <div role="status" style={{ textAlign: "center", padding: 40, color: "#f0a6a6", fontSize: "0.9rem" }}>
                {error}
              </div>
            ) : filtered.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: "#a89eb0", fontSize: "0.9rem" }}>
                {entries.length === 0 ? "No local memories stored yet. HINAA learns your preferences automatically." : "No matching memories."}
              </div>
            ) : (
              filtered.map((entry) => {
                const config = getCategoryConfig(entry.category);
                const Icon = config.icon;
                const isEditing = editingId === entry.id;
                const isConfirmingDelete = confirmDeleteId === entry.id;
                
                return (
                  <motion.div
                    key={entry.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      borderRadius: 12,
                      border: "1px solid rgba(255,255,255,0.08)",
                      padding: 16,
                      marginBottom: 12,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 12 }}>
                      <Icon size={16} color={config.color} style={{ marginTop: 2, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        {isEditing ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                            <textarea
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              style={{
                                width: "100%",
                                border: "1px solid rgba(236, 72, 153, 0.4)",
                                background: "rgba(0,0,0,0.2)",
                                color: "#fdf8ff",
                                borderRadius: 8,
                                padding: 8,
                                fontSize: "0.85rem",
                                fontFamily: "inherit",
                                resize: "vertical",
                                minHeight: 60,
                              }}
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveEdit(); }
                                if (e.key === "Escape") setEditingId(null);
                              }}
                            />
                            <div style={{ display: "flex", gap: 8, fontSize: "0.75rem" }}>
                              <label style={{ display: "flex", alignItems: "center", gap: 4, color: "#a89eb0" }}>
                                <input type="radio" checked={editExpiry === null} onChange={() => setEditExpiry(null)} /> Keep
                              </label>
                              <label style={{ display: "flex", alignItems: "center", gap: 4, color: "#a89eb0" }}>
                                <input type="radio" checked={editExpiry === 7} onChange={() => setEditExpiry(7)} /> 7d
                              </label>
                              <label style={{ display: "flex", alignItems: "center", gap: 4, color: "#a89eb0" }}>
                                <input type="radio" checked={editExpiry === 30} onChange={() => setEditExpiry(30)} /> 30d
                              </label>
                              <label style={{ display: "flex", alignItems: "center", gap: 4, color: "#a89eb0" }}>
                                <input type="radio" checked={editExpiry === 90} onChange={() => setEditExpiry(90)} /> 90d
                              </label>
                            </div>
                          </div>
                        ) : (
                          <div style={{ fontSize: "0.85rem", color: "#fdf8ff", lineHeight: 1.5 }}>
                            {entry.content}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: 10, marginTop: 10 }}>
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        <span style={{ fontSize: "0.65rem", color: config.color, fontWeight: 600, textTransform: "uppercase" }}>
                          {config.label}
                        </span>
                        {entry.expiresAt && (
                          <span style={{ fontSize: "0.65rem", color: "#ef4444" }}>
                            Expires: {new Date(entry.expiresAt).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      
                      {isConfirmingDelete ? (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button onClick={() => removeMemory(entry.id)} style={{ background: "#ef4444", color: "#fff", border: "none", borderRadius: 6, padding: "4px 10px", fontSize: "0.75rem", cursor: "pointer" }}>Delete</button>
                          <button onClick={() => setConfirmDeleteId(null)} style={{ background: "rgba(255,255,255,0.1)", color: "#fff", border: "none", borderRadius: 6, padding: "4px 10px", fontSize: "0.75rem", cursor: "pointer" }}>Cancel</button>
                        </div>
                      ) : (
                        <div style={{ display: "flex", gap: 4 }}>
                          <motion.button
                            onClick={() => isEditing ? saveEdit() : startEdit(entry)}
                            whileHover={{ scale: 1.1 }}
                            style={{ width: 28, height: 28, borderRadius: 6, border: "none", background: isEditing ? "rgba(16, 185, 129, 0.2)" : "transparent", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                          >
                            {isEditing ? <Check size={14} color="#10b981" /> : <Edit3 size={14} color="#a89eb0" />}
                          </motion.button>
                          <motion.button
                            onClick={() => setConfirmDeleteId(entry.id)}
                            whileHover={{ scale: 1.1 }}
                            style={{ width: 28, height: 28, borderRadius: 6, border: "none", background: "transparent", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                          >
                            <Trash2 size={14} color="#ef4444" />
                          </motion.button>
                        </div>
                      )}
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
