import React, { useState } from "react";
import { motion } from "framer-motion";
import { Palette, Copy, Check } from "lucide-react";
import { HINA_MOTION } from "../../motion/MOTION";
import type { ColorFields } from "../types";

interface ColorCardProps {
  data: ColorFields;
  onCommit?: (updated: ColorFields) => void;
  compact?: boolean;
}

export function ColorCard({ data, onCommit, compact = false }: ColorCardProps) {
  const [copiedHex, setCopiedHex] = useState(false);
  const [copiedRgb, setCopiedRgb] = useState(false);

  const copyToClipboard = (text: string, isHex: boolean) => {
    navigator.clipboard?.writeText(text);
    if (isHex) {
      setCopiedHex(true);
      setTimeout(() => setCopiedHex(false), 1200);
    } else {
      setCopiedRgb(true);
      setTimeout(() => setCopiedRgb(false), 1200);
    }
  };

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
              background: "rgba(74, 237, 217, 0.15)",
              color: "#4aedd9",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Palette size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>
            {data.name || "Color Inspector"}
          </span>
        </div>
        <span
          style={{
            fontSize: "0.72rem",
            padding: "2px 8px",
            borderRadius: 4,
            background: "rgba(255,255,255,0.06)",
            color: "rgba(255,255,255,0.6)",
          }}
        >
          sRGB
        </span>
      </div>

      {/* Swatch & Codes */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "12px 14px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
        }}
      >
        {/* Color preview box */}
        <div
          style={{
            width: 58,
            height: 58,
            borderRadius: 12,
            background: data.hex,
            boxShadow: `0 4px 16px ${data.hex}44`,
            border: "2px solid rgba(255,255,255,0.2)",
            flexShrink: 0,
          }}
        />

        {/* Values */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "monospace", fontSize: "1rem", fontWeight: 700 }}>
              {data.hex}
            </span>
            <button
              type="button"
              onClick={() => copyToClipboard(data.hex, true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: "3px 8px",
                borderRadius: 5,
                background: "rgba(255,255,255,0.06)",
                border: "none",
                color: copiedHex ? "#10b981" : "rgba(255,255,255,0.7)",
                fontSize: "0.72rem",
                cursor: "pointer",
              }}
            >
              {copiedHex ? <Check size={12} /> : <Copy size={12} />}
              <span>{copiedHex ? "Copied" : "Copy HEX"}</span>
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "monospace", fontSize: "0.82rem", color: "rgba(255,255,255,0.6)" }}>
              {data.rgb}
            </span>
            <button
              type="button"
              onClick={() => copyToClipboard(data.rgb, false)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: "3px 8px",
                borderRadius: 5,
                background: "rgba(255,255,255,0.06)",
                border: "none",
                color: copiedRgb ? "#10b981" : "rgba(255,255,255,0.7)",
                fontSize: "0.72rem",
                cursor: "pointer",
              }}
            >
              {copiedRgb ? <Check size={12} /> : <Copy size={12} />}
              <span>{copiedRgb ? "Copied" : "Copy RGB"}</span>
            </button>
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
            background: data.hex,
            color: "#000000",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Save Palette Color ↵</span>
        </button>
      )}
    </div>
  );
}
