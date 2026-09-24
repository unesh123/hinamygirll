import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  ChevronUp,
  X,
  Users,
  Timer,
  Calendar,
  CheckSquare,
  Globe,
  Bell,
  Dices,
  Palette,
  Image as ImageIcon,
  FileText,
  Zap,
} from "lucide-react";
import { HINA_MOTION } from "../../motion/MOTION";
import type { HinaCommittedAction } from "../types";
import { HinaSurface } from "./HinaSurface";

interface HinaActionStackProps {
  items: HinaCommittedAction[];
  onRemoveItem?: (id: string) => void;
  onUpdateItem?: (id: string, updatedDraft: any) => void;
  compact?: boolean;
}

export function HinaActionStack({
  items,
  onRemoveItem,
  onUpdateItem,
  compact = false,
}: HinaActionStackProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!items || items.length === 0) return null;

  const getActionIcon = (intent: string) => {
    switch (intent) {
      case "split":
        return <Users size={14} color="#4fb989" />;
      case "timer.start":
        return <Timer size={14} color="#eb6f92" />;
      case "event.create":
        return <Calendar size={14} color="#3b82f6" />;
      case "checklist.create":
        return <CheckSquare size={14} color="#a855f7" />;
      case "timezone.convert":
        return <Globe size={14} color="#0ea5e9" />;
      case "reminder.create":
        return <Bell size={14} color="#f59e0b" />;
      case "random.roll":
        return <Dices size={14} color="#f43f5e" />;
      case "color.inspect":
        return <Palette size={14} color="#4aedd9" />;
      case "image.job":
        return <ImageIcon size={14} color="#f36f9c" />;
      case "pdf.doc":
        return <FileText size={14} color="#ef4444" />;
      case "plan.run":
        return <Zap size={14} color="#eab308" />;
      case "browser.agent":
        return <Globe size={14} color="#6366f1" />;
      default:
        return <Zap size={14} color="#94a3b8" />;
    }
  };

  return (
    <motion.div
      layout
      transition={HINA_MOTION.settle}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "6px",
        width: "100%",
        maxWidth: 768,
        margin: "8px 0 12px 0",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 4px",
          marginBottom: 2,
        }}
      >
        <span
          style={{
            fontSize: "0.72rem",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--text-tertiary, rgba(255,255,255,0.4))",
          }}
        >
          Active Action Objects ({items.length})
        </span>
      </div>

      <AnimatePresence>
        {items.map((item) => {
          const isExpanded = expandedId === item.id;

          return (
            <motion.div
              key={item.id}
              layout
              layoutId={`action-${item.id}`}
              transition={HINA_MOTION.settle}
              style={{
                borderRadius: 10,
                background: "var(--bg-surface-raised, #18202a)",
                border: "1px solid var(--border-subtle, rgba(255,255,255,0.06))",
                overflow: "hidden",
              }}
            >
              {isExpanded ? (
                <div style={{ padding: "8px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      padding: "4px 8px 0",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedId(null)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "rgba(255,255,255,0.5)",
                        fontSize: "0.75rem",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <ChevronUp size={13} />
                      <span>Collapse to row</span>
                    </button>
                  </div>
                  <HinaSurface
                    draft={item.draft}
                    compact={compact}
                    onDismiss={() => setExpandedId(null)}
                    onCommit={(updated) => {
                      onUpdateItem?.(item.id, updated);
                      setExpandedId(null);
                    }}
                  />
                </div>
              ) : (
                /* Collapsed One-line Activity Row */
                <div
                  onClick={() => setExpandedId(item.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 14px",
                    cursor: "pointer",
                    userSelect: "none",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.background =
                      "rgba(255,255,255,0.04)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.background =
                      "transparent";
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: 6,
                        background: "rgba(255,255,255,0.06)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      {getActionIcon(item.draft.intent)}
                    </div>
                    <span
                      style={{
                        fontSize: "0.82rem",
                        fontWeight: 600,
                        color: "#ffffff",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {item.summaryText}
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: "rgba(255,255,255,0.06)",
                        color: "rgba(255,255,255,0.6)",
                        fontWeight: 600,
                      }}
                    >
                      {item.badgeLabel}
                    </span>

                    {onRemoveItem && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveItem(item.id);
                        }}
                        style={{
                          background: "none",
                          border: "none",
                          color: "rgba(255,255,255,0.4)",
                          cursor: "pointer",
                          padding: 2,
                        }}
                      >
                        <X size={13} />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </motion.div>
  );
}
