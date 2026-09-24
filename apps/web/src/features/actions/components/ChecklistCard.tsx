import React, { useState } from "react";
import { CheckSquare, Square, Plus, Check } from "lucide-react";
import type { ChecklistFields, ChecklistItem } from "../types";

interface ChecklistCardProps {
  data: ChecklistFields;
  onCommit?: (updated: ChecklistFields) => void;
  compact?: boolean;
}

export function ChecklistCard({ data, onCommit, compact = false }: ChecklistCardProps) {
  const [items, setItems] = useState<ChecklistItem[]>(data.items);
  const [newItemText, setNewItemText] = useState("");

  const toggleItem = (id: string) => {
    setItems((prev) =>
      prev.map((it) => (it.id === id ? { ...it, checked: !it.checked } : it))
    );
  };

  const addItem = () => {
    if (!newItemText.trim()) return;
    setItems((prev) => [
      ...prev,
      {
        id: `item-${Date.now()}`,
        text: newItemText.trim(),
        checked: false,
      },
    ]);
    setNewItemText("");
  };

  const completedCount = items.filter((i) => i.checked).length;

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
              background: "rgba(168, 85, 247, 0.15)",
              color: "#a855f7",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <CheckSquare size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>{data.title || "Checklist"}</span>
        </div>
        <span style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.5)" }}>
          {completedCount} of {items.length} done
        </span>
      </div>

      {/* Items list */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {items.map((item) => (
          <div
            key={item.id}
            onClick={() => toggleItem(item.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 12px",
              borderRadius: 8,
              background: item.checked ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.04)",
              cursor: "pointer",
              transition: "background 0.15s ease",
            }}
          >
            {item.checked ? (
              <CheckSquare size={16} color="#a855f7" />
            ) : (
              <Square size={16} color="rgba(255,255,255,0.3)" />
            )}
            <span
              style={{
                fontSize: "0.85rem",
                color: item.checked ? "rgba(255,255,255,0.4)" : "#ffffff",
                textDecoration: item.checked ? "line-through" : "none",
                fontWeight: item.checked ? 400 : 500,
              }}
            >
              {item.text}
            </span>
          </div>
        ))}
      </div>

      {/* Inline add item */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
        <input
          type="text"
          value={newItemText}
          onChange={(e) => setNewItemText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addItem()}
          placeholder="+ Add another item"
          style={{
            flex: 1,
            padding: "6px 10px",
            borderRadius: 6,
            background: "rgba(255,255,255,0.03)",
            border: "1px dashed rgba(255,255,255,0.15)",
            color: "#ffffff",
            fontSize: "0.8rem",
            outline: "none",
          }}
        />
        {newItemText.trim() && (
          <button
            type="button"
            onClick={addItem}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              background: "#a855f7",
              color: "#ffffff",
              border: "none",
              fontSize: "0.75rem",
              fontWeight: 650,
              cursor: "pointer",
            }}
          >
            Add
          </button>
        )}
      </div>

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() => onCommit({ ...data, items })}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            background: "#a855f7",
            color: "#ffffff",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Save Checklist ↵</span>
        </button>
      )}
    </div>
  );
}
