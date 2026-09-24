import React, { useState, useEffect } from "react";
import { Bell, AlertCircle, Clock, Check } from "lucide-react";
import type { ReminderFields } from "../types";

interface ReminderCardProps {
  data: ReminderFields;
  onCommit?: (updated: ReminderFields) => void;
  compact?: boolean;
}

export function ReminderCard({ data, onCommit, compact = false }: ReminderCardProps) {
  const [title, setTitle] = useState(data.title || "Pay rent");
  const [when, setWhen] = useState(data.when || "Tomorrow · 8:00 AM");
  const [isUrgent, setIsUrgent] = useState(Boolean(data.isUrgent));

  // Keep state synchronized with incoming typed/parsed data props
  useEffect(() => {
    if (data.title) setTitle(data.title);
    if (data.when) setWhen(data.when);
    setIsUrgent(Boolean(data.isUrgent));
  }, [data.title, data.when, data.isUrgent]);

  const displayTitle = title || data.title || "Pay rent";
  const displayWhen = when || data.when || "Tomorrow · 8:00 AM";

  return (
    <div
      style={{
        padding: compact ? "12px 14px" : "16px 20px",
        borderRadius: "14px",
        background: "var(--bg-surface-raised, #ffffff)",
        border: "1px solid var(--border-default, #e2e8f0)",
        boxShadow: "0 8px 30px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04)",
        color: "var(--text-primary, #0f172a)",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        width: "100%",
        maxWidth: 520,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: isUrgent ? "rgba(239, 68, 68, 0.15)" : "rgba(245, 158, 11, 0.15)",
              color: isUrgent ? "#dc2626" : "#d97706",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Bell size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>Reminder</span>
        </div>
        <button
          type="button"
          onClick={() => setIsUrgent(!isUrgent)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "2px 8px",
            borderRadius: 4,
            background: isUrgent ? "rgba(239, 68, 68, 0.15)" : "var(--surface-subtle, rgba(0,0,0,0.04))",
            color: isUrgent ? "#dc2626" : "var(--text-secondary, #475569)",
            border: isUrgent ? "1px solid rgba(239, 68, 68, 0.4)" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
            fontSize: "0.72rem",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <AlertCircle size={12} />
          <span>{isUrgent ? "Urgent Priority" : "Normal"}</span>
        </button>
      </div>

      {/* Main Task Title - Guaranteed High Contrast AA */}
      <div
        style={{
          fontSize: "1.2rem",
          fontWeight: 750,
          color: "var(--text-primary, #0f172a)",
          lineHeight: 1.3,
          wordBreak: "break-word",
        }}
      >
        {displayTitle}
      </div>

      {/* When badge */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderRadius: 8,
          background: "var(--surface-subtle, rgba(0,0,0,0.04))",
          border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
          fontSize: "0.85rem",
          fontWeight: 600,
          color: "var(--text-primary, #1e293b)",
        }}
      >
        <Clock size={15} color="#d97706" />
        <span>{displayWhen}</span>
      </div>

      {/* Commit button or Thread state */}
      {onCommit ? (
        <button
          type="button"
          onClick={() => onCommit({ title: displayTitle, when: displayWhen, isUrgent })}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "9px 14px",
            borderRadius: 8,
            background: isUrgent ? "#ef4444" : "#f59e0b",
            color: "#000000",
            border: "none",
            fontWeight: 750,
            fontSize: "0.84rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={15} strokeWidth={2.5} />
          <span>Set Reminder (Not Wired) ↵</span>
        </button>
      ) : (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.2)",
            marginTop: 4,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem", color: "#059669", fontWeight: 700 }}>
            <Check size={14} />
            <span>Reminder active in thread</span>
          </div>
          <span
            style={{
              fontSize: "0.72rem",
              color: "#64748b",
              fontWeight: 750,
              background: "rgba(0,0,0,0.06)",
              padding: "2px 8px",
              borderRadius: 4,
              letterSpacing: "0.02em",
            }}
          >
            NOT WIRED
          </span>
        </div>
      )}
    </div>
  );
}
