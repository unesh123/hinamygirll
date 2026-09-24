import React, { useEffect, useCallback } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { X, CornerDownLeft } from "lucide-react";
import { HINA_MOTION, getHinaTransition } from "../../motion/MOTION";
import type { HinaActionDraft, ActionFields } from "../types";

// Individual cards
import { SplitCard } from "./SplitCard";
import { TimerCard } from "./TimerCard";
import { EventCard } from "./EventCard";
import { ChecklistCard } from "./ChecklistCard";
import { TimezoneCard } from "./TimezoneCard";
import { ReminderCard } from "./ReminderCard";
import { RandomCard } from "./RandomCard";
import { ColorCard } from "./ColorCard";
import { ImageJobCard } from "./ImageJobCard";
import { PdfCard } from "./PdfCard";
import { PlanCard } from "./PlanCard";
import { BrowserAgentCard } from "./BrowserAgentCard";

interface HinaSurfaceProps {
  draft: HinaActionDraft | null;
  onCommit: (draft: HinaActionDraft) => void;
  onDismiss: () => void;
  compact?: boolean;
}

export function HinaSurface({ draft, onCommit, onDismiss, compact = false }: HinaSurfaceProps) {
  const shouldReduceMotion = useReducedMotion();
  const transition = getHinaTransition(shouldReduceMotion, "spring");

  // Global Esc key listener to collapse the active card back to pill
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && draft) {
        e.preventDefault();
        onDismiss();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [draft, onDismiss]);

  if (!draft) return null;

  const renderCardContent = () => {
    switch (draft.intent) {
      case "split":
        return (
          <SplitCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "split", data: updated } })}
          />
        );
      case "timer.start":
        return (
          <TimerCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "timer.start", data: updated } })}
          />
        );
      case "event.create":
        return (
          <EventCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "event.create", data: updated } })}
          />
        );
      case "checklist.create":
        return (
          <ChecklistCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "checklist.create", data: updated } })}
          />
        );
      case "timezone.convert":
        return (
          <TimezoneCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "timezone.convert", data: updated } })}
          />
        );
      case "reminder.create":
        return (
          <ReminderCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "reminder.create", data: updated } })}
          />
        );
      case "random.roll":
        return (
          <RandomCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "random.roll", data: updated } })}
          />
        );
      case "color.inspect":
        return (
          <ColorCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "color.inspect", data: updated } })}
          />
        );
      case "image.job":
        return (
          <ImageJobCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "image.job", data: updated } })}
          />
        );
      case "pdf.doc":
        return (
          <PdfCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "pdf.doc", data: updated } })}
          />
        );
      case "plan.run":
        return (
          <PlanCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "plan.run", data: updated } })}
          />
        );
      case "browser.agent":
        return (
          <BrowserAgentCard
            data={draft.fields.data as any}
            compact={compact}
            onCommit={(updated) => onCommit({ ...draft, fields: { intent: "browser.agent", data: updated } })}
          />
        );
      default:
        return null;
    }
  };

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={draft.id}
        layout
        layoutId={`action-${draft.id}`}
        initial={{ opacity: 0, scale: 0.96, y: -8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: -4 }}
        transition={transition}
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          transformOrigin: "top center",
          position: "relative",
          zIndex: 40,
          margin: "8px 0",
        }}
      >
        {/* Floating action bar controls (Esc hint & dismiss) */}
        <div
          style={{
            position: "absolute",
            top: 8,
            right: 8,
            display: "flex",
            alignItems: "center",
            gap: 6,
            zIndex: 10,
          }}
        >
          <span
            style={{
              fontSize: "0.68rem",
              color: "rgba(255,255,255,0.4)",
              background: "rgba(0,0,0,0.3)",
              padding: "2px 6px",
              borderRadius: 4,
            }}
          >
            Esc to cancel
          </span>
          <button
            type="button"
            onClick={onDismiss}
            title="Dismiss action"
            style={{
              width: 24,
              height: 24,
              borderRadius: "50%",
              background: "rgba(255,255,255,0.1)",
              border: "none",
              color: "rgba(255,255,255,0.6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <X size={13} />
          </button>
        </div>

        {renderCardContent()}
      </motion.div>
    </AnimatePresence>
  );
}
