import React from "react";
import { Globe, ArrowRight, Clock, Check } from "lucide-react";
import type { TimezoneFields } from "../types";

interface TimezoneCardProps {
  data: TimezoneFields;
  onCommit?: (updated: TimezoneFields) => void;
  compact?: boolean;
}

export function TimezoneCard({ data, onCommit, compact = false }: TimezoneCardProps) {
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
              background: "rgba(14, 165, 233, 0.15)",
              color: "#0ea5e9",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Globe size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>Time Zone Converter</span>
        </div>
        {data.isNextDay && (
          <span
            style={{
              fontSize: "0.72rem",
              padding: "2px 8px",
              borderRadius: 4,
              background: "rgba(245, 158, 11, 0.15)",
              color: "#fbbf24",
              fontWeight: 700,
            }}
          >
            +1 Day Next Morning
          </span>
        )}
      </div>

      {/* Dual Clocks */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
          gap: 12,
        }}
      >
        {/* Source */}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: "0.72rem", color: "rgba(255,255,255,0.5)", textTransform: "uppercase" }}>
            {data.sourceTz}
          </div>
          <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#ffffff", marginTop: 2 }}>
            {data.sourceTime}
          </div>
        </div>

        {/* Transition arrow */}
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.06)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "rgba(255,255,255,0.6)",
          }}
        >
          <ArrowRight size={16} />
        </div>

        {/* Target */}
        <div style={{ flex: 1, textAlign: "right" }}>
          <div style={{ fontSize: "0.72rem", color: "#0ea5e9", textTransform: "uppercase", fontWeight: 700 }}>
            {data.targetTz}
          </div>
          <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#0ea5e9", marginTop: 2 }}>
            {data.targetTime}
          </div>
        </div>
      </div>

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() => onCommit(data)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            background: "#0ea5e9",
            color: "#ffffff",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Save Time ↵</span>
        </button>
      )}
    </div>
  );
}
