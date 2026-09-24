import React, { useState } from "react";
import { Bell, AlertCircle, Clock, Check } from "lucide-react";
import type { ReminderFields } from "../types";

interface ReminderCardProps {
  data: ReminderFields;
  onCommit?: (updated: ReminderFields) => void;
  compact?: boolean;
}

export function ReminderCard({ data, onCommit, compact = false }: ReminderCardProps) {
  const [title, setTitle] = useState(data.title);
  const [when, setWhen] = useState(data.when);
  const [isUrgent, setIsUrgent] = useState(data.isUrgent);

  return (
    <div
      style={{
        padding: compact ? "12px 14px" : "16px 20px",
        borderRadius: "14px",
        background: "var(--bg-surface-raised, #18202a)",
        border: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
        boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
        color: "#ffffff",
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
              background: isUrgent ? "rgba(239, 68, 68, 0.2)" : "rgba(245, 158, 11, 0.15)",
              color: isUrgent ? "#ef4444" : "#f59e0b",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Bell size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>Reminder</span>
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
            background: isUrgent ? "rgba(239, 68, 68, 0.2)" : "rgba(255,255,255,0.06)",
            color: isUrgent ? "#ef4444" : "rgba(255,255,255,0.6)",
            border: isUrgent ? "1px solid rgba(239, 68, 68, 0.4)" : "none",
            fontSize: "0.72rem",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <AlertCircle size={12} />
          <span>{isUrgent ? "Urgent Priority" : "Normal"}</span>
        </button>
      </div>

      {/* Main Task Title */}
      <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#ffffff" }}>
        {title}
      </div>

      {/* When badge */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderRadius: 8,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
          fontSize: "0.82rem",
          color: "rgba(255,255,255,0.85)",
        }}
      >
        <Clock size={14} color="#f59e0b" />
        <span>{when}</span>
      </div>

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() => onCommit({ title, when, isUrgent })}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            background: isUrgent ? "#ef4444" : "#f59e0b",
            color: "#000000",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Set Reminder ↵</span>
        </button>
      )}
    </div>
  );
}
