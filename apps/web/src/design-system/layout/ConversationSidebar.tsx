import { useState, useEffect, useCallback, useMemo } from "react";
import { HINAA_DEV_USER } from "../../lib/hinaaIdentity";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircle, Trash2, Pencil, Check, X, Search } from "lucide-react";

interface ConversationItem {
  id: string;
  title: string;
  created_at: string | null;
  message_count: number;
  last_message_preview: string;
  companion_id: string;
}

interface ConversationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
}

function groupByDate(conversations: ConversationItem[]): Record<string, ConversationItem[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, ConversationItem[]> = {};

  for (const c of conversations) {
    const d = c.created_at ? new Date(c.created_at) : new Date(0);
    let label: string;
    if (d >= today) label = "Today";
    else if (d >= yesterday) label = "Yesterday";
    else if (d >= weekAgo) label = "Previous 7 days";
    else label = "Older";

    if (!groups[label]) groups[label] = [];
    groups[label].push(c);
  }

  return groups;
}

export function ConversationSidebar({
  isOpen,
  onClose,
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/conversations?limit=50", {
        headers: { "X-HINAA-Dev-User": HINAA_DEV_USER },
      });
      if (res.ok) {
        const data = await res.json();
        // GET /v1/conversations answers with a bare array, not an envelope.
        const items: ConversationItem[] = Array.isArray(data) ? data : data?.conversations ?? [];
        setConversations(items);
      }
    } catch (err) {
      console.error("Failed to fetch conversations:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) fetchConversations();
  }, [isOpen, fetchConversations]);

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.last_message_preview.toLowerCase().includes(q),
    );
  }, [conversations, searchQuery]);

  const grouped = useMemo(() => groupByDate(filtered), [filtered]);
  const groupOrder = ["Today", "Yesterday", "Previous 7 days", "Older"];

  const handleRename = async (id: string) => {
    if (!editTitle.trim()) {
      setEditingId(null);
      return;
    }
    try {
      await fetch(`/api/v1/conversations/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-HINAA-Dev-User": HINAA_DEV_USER,
        },
        body: JSON.stringify({ title: editTitle.trim() }),
      });
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: editTitle.trim() } : c)),
      );
    } catch {
      // Silently fail
    }
    setEditingId(null);
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`/api/v1/privacy/conversations/${id}`, {
        method: "DELETE",
        headers: { "X-HINAA-Dev-User": HINAA_DEV_USER },
      });
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (onDeleteConversation) onDeleteConversation(id);
    } catch {
      // Silently fail
    }
    setDeleteConfirmId(null);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.3)",
              zIndex: 998,
            }}
          />
          {/* Sidebar panel */}
          <motion.aside
            data-testid="conversation-history-panel"
            initial={{ x: -320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -320, opacity: 0 }}
            transition={{ type: "spring", stiffness: 350, damping: 35 }}
            style={{
              position: "fixed",
              top: 0,
              left: 56,
              bottom: 0,
              width: 320,
              background: "var(--bg-primary)",
              borderRight: "1px solid var(--border-default)",
              boxShadow: "var(--shadow-lg)",
              zIndex: 999,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* Header */}
            <div
              style={{
                padding: "var(--space-4)",
                borderBottom: "1px solid var(--border-subtle)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span
                style={{
                  fontSize: "var(--text-base)",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                }}
              >
                Conversations
              </span>
              <button
                onClick={onClose}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-tertiary)",
                  cursor: "pointer",
                  padding: 4,
                  borderRadius: "var(--radius-sm)",
                }}
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            {/* Search */}
            <div style={{ padding: "var(--space-2) var(--space-4)" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  padding: "var(--space-2) var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <Search size={14} color="var(--text-tertiary)" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search conversations..."
                  style={{
                    background: "transparent",
                    border: "none",
                    outline: "none",
                    color: "var(--text-primary)",
                    fontSize: "var(--text-sm)",
                    fontFamily: "inherit",
                    width: "100%",
                  }}
                />
              </div>
            </div>

            {/* Conversation list */}
            <div style={{ flex: 1, overflowY: "auto", padding: "0 var(--space-2)" }}>
              {loading ? (
                <div
                  style={{
                    padding: "var(--space-6)",
                    textAlign: "center",
                    color: "var(--text-tertiary)",
                    fontSize: "var(--text-sm)",
                  }}
                >
                  Loading...
                </div>
              ) : filtered.length === 0 ? (
                <div
                  style={{
                    padding: "var(--space-6)",
                    textAlign: "center",
                    color: "var(--text-tertiary)",
                    fontSize: "var(--text-sm)",
                  }}
                >
                  {searchQuery ? "No matching conversations" : "No conversations yet. Start chatting!"}
                </div>
              ) : (
                groupOrder
                  .filter((label) => grouped[label]?.length)
                  .map((label) => (
                    <div key={label} style={{ marginBottom: "var(--space-3)" }}>
                      <div
                        style={{
                          fontSize: "var(--text-xs)",
                          fontWeight: 600,
                          color: "var(--text-tertiary)",
                          padding: "var(--space-2) var(--space-3)",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                        }}
                      >
                        {label}
                      </div>
                      {grouped[label].map((convo) => (
                        <motion.button
                          key={convo.id}
                          type="button"
                          data-testid="conversation-row"
                          onClick={() => {
                            if (editingId !== convo.id && deleteConfirmId !== convo.id) {
                              onSelectConversation(convo.id);
                            }
                          }}
                          whileHover={{ backgroundColor: "var(--bg-surface-raised)" }}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "var(--space-3)",
                            padding: "var(--space-2) var(--space-3)",
                            borderRadius: "var(--radius-md)",
                            border: "none",
                            background:
                              convo.id === activeConversationId
                                ? "var(--accent-pale)"
                                : "transparent",
                            color:
                              convo.id === activeConversationId
                                ? "var(--accent)"
                                : "var(--text-primary)",
                            cursor: "pointer",
                            width: "100%",
                            textAlign: "left",
                            fontSize: "var(--text-sm)",
                            fontFamily: "var(--font-body)",
                            position: "relative",
                            minHeight: 44,
                          }}
                        >
                          <MessageCircle
                            size={16}
                            style={{ flexShrink: 0, opacity: 0.6 }}
                          />
                          <div
                            style={{
                              flex: 1,
                              overflow: "hidden",
                              display: "flex",
                              flexDirection: "column",
                              gap: 2,
                            }}
                          >
                            {editingId === convo.id ? (
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 4,
                                }}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <input
                                  type="text"
                                  value={editTitle}
                                  onChange={(e) => setEditTitle(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") handleRename(convo.id);
                                    if (e.key === "Escape") setEditingId(null);
                                  }}
                                  autoFocus
                                  style={{
                                    background: "var(--bg-surface)",
                                    border: "1px solid var(--border-default)",
                                    borderRadius: "var(--radius-sm)",
                                    padding: "2px 6px",
                                    color: "var(--text-primary)",
                                    fontSize: "var(--text-sm)",
                                    width: "100%",
                                    outline: "none",
                                  }}
                                />
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRename(convo.id);
                                  }}
                                  style={{
                                    background: "none",
                                    border: "none",
                                    cursor: "pointer",
                                    color: "var(--success)",
                                    padding: 2,
                                  }}
                                >
                                  <Check size={14} />
                                </button>
                              </div>
                            ) : (
                              <>
                                <span
                                  style={{
                                    fontWeight: 500,
                                    whiteSpace: "nowrap",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                  }}
                                >
                                  {convo.title}
                                </span>
                                <span
                                  style={{
                                    fontSize: "var(--text-xs)",
                                    color: "var(--text-tertiary)",
                                    whiteSpace: "nowrap",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                  }}
                                >
                                  {convo.message_count} {convo.message_count === 1 ? "message" : "messages"}
                                </span>
                              </>
                            )}
                          </div>

                          {/* Action buttons on hover */}
                          {editingId !== convo.id && (
                            <div
                              className="convo-actions"
                              style={{
                                display: "flex",
                                gap: 2,
                                opacity: 0,
                                transition: "opacity 0.15s",
                              }}
                            >
                              {deleteConfirmId === convo.id ? (
                                <>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDelete(convo.id);
                                    }}
                                    style={{
                                      background: "rgba(239,68,68,0.1)",
                                      border: "none",
                                      borderRadius: "var(--radius-sm)",
                                      color: "#ef4444",
                                      cursor: "pointer",
                                      padding: "2px 6px",
                                      fontSize: "var(--text-xs)",
                                      fontWeight: 600,
                                    }}
                                  >
                                    Delete
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setDeleteConfirmId(null);
                                    }}
                                    style={{
                                      background: "none",
                                      border: "none",
                                      color: "var(--text-tertiary)",
                                      cursor: "pointer",
                                      padding: 2,
                                    }}
                                  >
                                    <X size={12} />
                                  </button>
                                </>
                              ) : (
                                <>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setEditingId(convo.id);
                                      setEditTitle(convo.title);
                                    }}
                                    style={{
                                      background: "none",
                                      border: "none",
                                      color: "var(--text-tertiary)",
                                      cursor: "pointer",
                                      padding: 2,
                                    }}
                                    title="Rename"
                                  >
                                    <Pencil size={12} />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setDeleteConfirmId(convo.id);
                                    }}
                                    style={{
                                      background: "none",
                                      border: "none",
                                      color: "var(--text-tertiary)",
                                      cursor: "pointer",
                                      padding: 2,
                                    }}
                                    title="Delete"
                                  >
                                    <Trash2 size={12} />
                                  </button>
                                </>
                              )}
                            </div>
                          )}
                        </motion.button>
                      ))}
                    </div>
                  ))
              )}
            </div>
          </motion.aside>

          {/* Hover styles */}
          <style>{`
            .convo-actions { opacity: 0 !important; }
            button:hover > .convo-actions { opacity: 1 !important; }
          `}</style>
        </>
      )}
    </AnimatePresence>
  );
}
