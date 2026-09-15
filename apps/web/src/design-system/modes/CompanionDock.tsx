import React, { useState, useRef } from "react";
import { motion } from "framer-motion";
import {
  Sparkles,
  Maximize2,
  Minimize2,
  X,
  Mic,
  Square,
} from "lucide-react";
import { VRMAvatar } from "../../features/avatar/VRMAvatar";
import { AvatarModelPicker } from "../../features/avatar/AvatarModelPicker";
import { AVATAR_REGISTRY } from "../../features/avatar/avatarRegistry";
import type { PresenceMode } from "../../components/ui/AvatarPresence";
import type { CompanionId, CompanionState } from "../../features/companion/types";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";

export type DockMode = "right" | "left" | "floating" | "compact" | "hidden";

export interface CompanionDockProps {
  dockMode: DockMode;
  onChangeDockMode: (mode: DockMode) => void;
  companionId?: CompanionId;
  companionState?: CompanionState;
  plan?: AssistantTurnPlan;
  avatarModel?: string;
  avatarMode?: PresenceMode;
  companionName?: string;
  jawEnergy?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEvents?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  speechBridge?: React.MutableRefObject<any>;
  onSelectModel?: (url: string) => void;
  onOpenAvatarLab?: () => void;
  isVoiceActive?: boolean;
  onToggleVoice?: () => void;
  streamingText?: string;
  partialTranscript?: string;
  lastAssistantText?: string;
}

export const CompanionDock: React.FC<CompanionDockProps> = ({
  dockMode,
  onChangeDockMode,
  companionId = "hinaa",
  companionState = "idle",
  plan,
  avatarModel,
  avatarMode = "half",
  companionName = "Hinaa",
  jawEnergy,
  speakingRef,
  visemeEvents,
  audioStartTimeRef,
  speechBridge,
  onSelectModel,
  onOpenAvatarLab,
  isVoiceActive = false,
  onToggleVoice,
  streamingText = "",
  partialTranscript = "",
  lastAssistantText = "",
}) => {
  const [showModelPicker, setShowModelPicker] = useState(false);
  const modelPickerTriggerRef = useRef<HTMLButtonElement>(null);

  const currentAvatarDef = AVATAR_REGISTRY.find((a) => a.fileUrl === avatarModel || a.id === avatarModel);
  const currentModelName = currentAvatarDef?.name || "Hinaa (Original)";

  if (dockMode === "hidden") {
    return null;
  }

  /* ── Compact Mini Dock Mode ──────────────────────────── */
  if (dockMode === "compact") {
    return (
      <motion.div
        data-testid="work-companion-panel"
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        style={{
          position: "fixed",
          bottom: 90,
          right: 24,
          width: 200,
          height: 250,
          borderRadius: 16,
          overflow: "hidden",
          background: "var(--bg-surface, #121215)",
          border: "1px solid var(--border-default, rgba(255,255,255,0.15))",
          boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
          zIndex: 45,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{
          padding: "4px 8px",
          background: "rgba(0,0,0,0.4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          zIndex: 10,
        }}>
          <span style={{ fontSize: "11px", fontWeight: 700, color: "#fff" }}>{companionName}</span>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              onClick={() => onChangeDockMode("right")}
              title="Expand Dock"
              style={{ background: "none", border: "none", color: "#a1a1aa", cursor: "pointer", padding: 2 }}
            >
              <Maximize2 size={12} />
            </button>
            <button
              onClick={() => onChangeDockMode("hidden")}
              title="Hide"
              style={{ background: "none", border: "none", color: "#a1a1aa", cursor: "pointer", padding: 2 }}
            >
              <X size={12} />
            </button>
          </div>
        </div>

        <div style={{ flex: 1, position: "relative" }}>
          <VRMAvatar
            key={`vrm-${avatarModel || "default"}`}
            companionId={companionId || "hinaa"}
            state={companionState}
            plan={plan}
            reducedMotion={false}
            textOnly={false}
            jawEnergy={jawEnergy}
            speakingRef={speakingRef}
            visemeEvents={visemeEvents}
            audioStartTimeRef={audioStartTimeRef}
            speechBridge={speechBridge}
            modelUrl={avatarModel ?? null}
            closeUp={true}
          />
        </div>
      </motion.div>
    );
  }

  /* ── Right, Left, and Floating Modes ─────────────────── */
  const isFloating = dockMode === "floating";
  const isLeft = dockMode === "left";

  let panelStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    background: "var(--bg-surface)",
    borderLeft: dockMode === "right" ? "1px solid var(--border-subtle)" : undefined,
    borderRight: dockMode === "left" ? "1px solid var(--border-subtle)" : undefined,
    zIndex: isFloating ? 50 : 10,
    flexShrink: 0,
    overflow: "hidden",
  };

  if (isFloating) {
    panelStyle = {
      ...panelStyle,
      position: "absolute",
      top: 16,
      right: 16,
      width: "320px",
      height: "440px",
      borderRadius: "var(--radius-xl, 16px)",
      border: "1px solid var(--border-default)",
      boxShadow: "0 10px 25px rgba(0,0,0,0.3)",
    };
  } else if (isLeft) {
    panelStyle = {
      ...panelStyle,
      position: "relative",
      width: 320,
      left: "0px",
      order: -1,
      height: "100%",
    };
  } else {
    panelStyle = {
      ...panelStyle,
      position: "relative",
      width: 320,
      right: "0px",
      order: 1,
      height: "100%",
    };
  }

  return (
    <aside
      data-testid="work-companion-panel"
      style={panelStyle}
      aria-label="Companion avatar panel"
    >
      {/* Companion Panel Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          borderBottom: "1px solid var(--border-subtle)",
          background: "var(--bg-surface-raised)",
          flexShrink: 0,
        }}
      >
        {/* Model Switcher Button */}
        <div style={{ position: "relative" }}>
          <button
            ref={modelPickerTriggerRef}
            type="button"
            aria-label="Switch 3D Avatar Model"
            onClick={() => setShowModelPicker((prev) => !prev)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 8px",
              borderRadius: "var(--radius-sm, 6px)",
              border: "1px solid var(--border-default)",
              background: "var(--bg-surface)",
              color: "var(--text-primary)",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Sparkles size={12} color="var(--accent)" />
            <span>{currentModelName}</span>
          </button>
          <AvatarModelPicker
            isOpen={showModelPicker}
            onClose={() => setShowModelPicker(false)}
            triggerRef={modelPickerTriggerRef}
            currentModel={avatarModel}
            onSelectModel={(url) => {
              onSelectModel?.(url);
              setShowModelPicker(false);
            }}
            onOpenAvatarLab={onOpenAvatarLab}
          />
        </div>

        {/* Dock and Close controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <button
            type="button"
            aria-label="Dock Left"
            title="Dock Left"
            onClick={() => onChangeDockMode("left")}
            style={{
              padding: "4px 6px",
              borderRadius: 4,
              border: "none",
              background: dockMode === "left" ? "var(--accent-pale)" : "transparent",
              color: dockMode === "left" ? "var(--accent)" : "var(--text-tertiary)",
              cursor: "pointer",
              fontSize: "0.7rem",
            }}
          >
            Dock Left
          </button>
          <button
            type="button"
            aria-label="Float Companion"
            title="Float Companion"
            onClick={() => onChangeDockMode("floating")}
            style={{
              padding: "4px 6px",
              borderRadius: 4,
              border: "none",
              background: dockMode === "floating" ? "var(--accent-pale)" : "transparent",
              color: dockMode === "floating" ? "var(--accent)" : "var(--text-tertiary)",
              cursor: "pointer",
              fontSize: "0.7rem",
            }}
          >
            Float Companion
          </button>
          <button
            type="button"
            aria-label="Dock Right"
            title="Dock Right"
            onClick={() => onChangeDockMode("right")}
            style={{
              padding: "4px 6px",
              borderRadius: 4,
              border: "none",
              background: dockMode === "right" ? "var(--accent-pale)" : "transparent",
              color: dockMode === "right" ? "var(--accent)" : "var(--text-tertiary)",
              cursor: "pointer",
              fontSize: "0.7rem",
            }}
          >
            Dock Right
          </button>
          <button
            type="button"
            aria-label="Hide Companion"
            title="Hide Companion"
            onClick={() => onChangeDockMode("hidden")}
            style={{
              padding: "4px 6px",
              borderRadius: 4,
              border: "none",
              background: "transparent",
              color: "var(--text-tertiary)",
              cursor: "pointer",
              fontSize: "0.7rem",
            }}
          >
            Hide Companion
          </button>
        </div>
      </div>

      {/* Companion Avatar View Container */}
      <div style={{ flex: 1, position: "relative", minHeight: 240, overflow: "hidden" }}>
        <VRMAvatar
          companionId={companionId || "hinaa"}
          state={companionState}
          plan={plan}
          reducedMotion={false}
          textOnly={false}
          jawEnergy={jawEnergy}
          speakingRef={speakingRef}
          visemeEvents={visemeEvents}
          audioStartTimeRef={audioStartTimeRef}
          speechBridge={speechBridge}
          modelUrl={avatarModel ?? null}
          closeUp={avatarMode !== "full"}
        />

        {/* Live speech feedback */}
        {(streamingText || partialTranscript || lastAssistantText) && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              position: "absolute",
              bottom: 12,
              left: 12,
              right: 12,
              padding: "8px 12px",
              borderRadius: 12,
              background: "rgba(18,18,21,0.85)",
              backdropFilter: "blur(12px)",
              border: "1px solid rgba(255,255,255,0.1)",
              fontSize: "11px",
              lineHeight: 1.4,
              color: "#f4f4f5",
              maxHeight: 70,
              overflowY: "auto",
              zIndex: 15,
            }}
          >
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent, #ec4899)", marginBottom: 2 }}>
              {companionName}
            </div>
            <div>{streamingText || partialTranscript || lastAssistantText}</div>
          </motion.div>
        )}
      </div>
    </aside>
  );
};
