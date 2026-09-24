import React from "react";
import { motion } from "framer-motion";
import { Sparkles, X, ArrowRight, Bell, ImageIcon, Users, Clock, ListTodo, Dice5, Palette } from "lucide-react";
import type { HinaObject } from "../types";

interface ComposerSuggestionStripProps {
  suggestion: HinaObject;
  onAdopt: () => void;
  onDismiss: () => void;
  compact?: boolean;
}

export function ComposerSuggestionStrip({
  suggestion,
  onAdopt,
  onDismiss,
  compact = false,
}: ComposerSuggestionStripProps) {
  let Icon = Sparkles;
  let accentColor = "#6366f1";
  let title = suggestion.title || "Action Available";
  let preview = suggestion.suggestionText || suggestion.description || "";

  if (suggestion.capabilityId.startsWith("reminder")) {
    Icon = Bell;
    accentColor = "#d97706";
    title = "Create reminder";
    const data = suggestion.fields as any;
    if (data?.title) {
      preview = `${data.when || "Tomorrow"} · ${data.title}`;
    }
  } else if (suggestion.capabilityId.startsWith("image")) {
    Icon = ImageIcon;
    accentColor = "#db2777";
    title = "Generate image";
    const data = suggestion.fields as any;
    if (data?.prompt) {
      preview = data.prompt;
    }
  } else if (suggestion.capabilityId === "split") {
    Icon = Users;
    accentColor = "#059669";
    title = "Split expense";
    const data = suggestion.fields as any;
    if (data?.perPerson) {
      preview = `${data.currency || "₹"}${data.perPerson} each · ${data.peopleCount || 3} people`;
    }
  } else if (suggestion.capabilityId.startsWith("timer")) {
    Icon = Clock;
    accentColor = "#2563eb";
    title = "Start timer";
    const data = suggestion.fields as any;
    if (data?.durationSeconds) {
      preview = `${Math.round(data.durationSeconds / 60)} minutes · ${data.label || "Focus"}`;
    }
  } else if (suggestion.capabilityId.startsWith("checklist")) {
    Icon = ListTodo;
    accentColor = "#7c3aed";
    title = "Create checklist";
    const data = suggestion.fields as any;
    if (data?.title) {
      preview = `${data.title} (${data.items?.length || 0} items)`;
    }
  } else if (suggestion.capabilityId.startsWith("random")) {
    Icon = Dice5;
    accentColor = "#ea580c";
    title = "Random roll";
  } else if (suggestion.capabilityId.startsWith("color")) {
    Icon = Palette;
    accentColor = "#0284c7";
    title = "Inspect color";
  }

  const rgbColor = accentColor === "#d97706" ? "217, 119, 6" : accentColor === "#db2777" ? "219, 39, 119" : "5, 150, 105";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.16 }}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 10,
        padding: compact ? "6px 10px" : "8px 14px",
        borderRadius: "10px",
        background: "var(--bg-surface-raised, #ffffff)",
        border: "1px solid var(--border-default, #e2e8f0)",
        boxShadow: "0 4px 16px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)",
        cursor: "pointer",
        maxWidth: 580,
        width: "100%",
        marginBottom: 8,
      }}
      onClick={onAdopt}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flex: 1 }}>
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: 6,
            background: `rgba(${rgbColor}, 0.12)`,
            color: accentColor,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Icon size={13} />
        </div>

        <div style={{ display: "flex", alignItems: "baseline", gap: 6, minWidth: 0, overflow: "hidden" }}>
          <span
            style={{
              fontSize: "0.82rem",
              fontWeight: 750,
              color: "var(--text-primary, #0f172a)",
              whiteSpace: "nowrap",
            }}
          >
            ✦ {title}
          </span>
          {preview && (
            <span
              style={{
                fontSize: "0.78rem",
                color: "var(--text-secondary, #64748b)",
                fontWeight: 500,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              · {preview}
            </span>
          )}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onAdopt();
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "3px 8px",
            borderRadius: 6,
            background: "var(--surface-subtle, rgba(0,0,0,0.04))",
            border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
            color: accentColor,
            fontSize: "0.72rem",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <span>Tab to configure</span>
          <ArrowRight size={11} />
        </button>

        <button
          type="button"
          aria-label="Dismiss suggestion"
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          style={{
            background: "none",
            border: "none",
            color: "var(--text-tertiary, #94a3b8)",
            cursor: "pointer",
            padding: 3,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 4,
          }}
        >
          <X size={13} />
        </button>
      </div>
    </motion.div>
  );
}
