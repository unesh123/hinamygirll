import { useState, useRef, useCallback, type KeyboardEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Mic,
  Paperclip,
  Globe,
  Sparkles,
  Code,
  FileText,
  Brain,
  Monitor,
  StopCircle,
  X,
  Zap,
} from "lucide-react";

export type PowerUpId =
  | "web-research"
  | "humanizer"
  | "code"
  | "pc-control"
  | "files"
  | "creative"
  | "data"
  | "memory";

export interface PowerUp {
  id: PowerUpId;
  label: string;
  icon: React.ReactNode;
  color: string;
  colorSoft: string;
  enabled: boolean;
}

export const DEFAULT_POWER_UPS: PowerUp[] = [
  { id: "web-research", label: "Web Research", icon: <Globe size={14} />, color: "#4FB989", colorSoft: "rgba(79, 185, 137, 0.12)", enabled: false },
  { id: "humanizer", label: "Humanizer", icon: <Sparkles size={14} />, color: "#5B9DCF", colorSoft: "rgba(91, 157, 207, 0.12)", enabled: false },
  { id: "code", label: "Code", icon: <Code size={14} />, color: "#B8A7F2", colorSoft: "rgba(184, 167, 242, 0.12)", enabled: false },
  { id: "pc-control", label: "PC Control", icon: <Monitor size={14} />, color: "#E9A23B", colorSoft: "rgba(233, 162, 59, 0.12)", enabled: false },
  { id: "files", label: "Files", icon: <FileText size={14} />, color: "#9CCFEA", colorSoft: "rgba(156, 207, 234, 0.12)", enabled: false },
  { id: "creative", label: "Creative", icon: <Zap size={14} />, color: "#F36F9C", colorSoft: "rgba(243, 111, 156, 0.12)", enabled: false },
  { id: "data", label: "Data", icon: <Brain size={14} />, color: "#9EDFC8", colorSoft: "rgba(158, 223, 200, 0.12)", enabled: false },
  { id: "memory", label: "Memory", icon: <Brain size={14} />, color: "#B8A7F2", colorSoft: "rgba(184, 167, 242, 0.12)", enabled: false },
];

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onVoiceToggle?: () => void;
  onStop?: () => void;
  isGenerating?: boolean;
  isVoiceActive?: boolean;
  disabled?: boolean;
  powerUps?: PowerUp[];
  onPowerUpToggle?: (id: PowerUpId) => void;
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  onVoiceToggle,
  onStop,
  isGenerating = false,
  isVoiceActive = false,
  disabled = false,
  powerUps = DEFAULT_POWER_UPS,
  onPowerUpToggle,
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [showAllPowerUps, setShowAllPowerUps] = useState(false);

  const activePowerUps = powerUps.filter((p) => p.enabled);
  const visiblePowerUps = showAllPowerUps ? powerUps : powerUps.slice(0, 4);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (isGenerating) {
          onStop?.();
        } else if (value.trim()) {
          onSend();
        }
      }
    },
    [value, isGenerating, onSend, onStop]
  );

  const handleInput = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 180) + "px";
  }, []);

  return (
    <div className="sakura-composer-wrapper">
      {/* Active power-up chips */}
      <AnimatePresence>
        {activePowerUps.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--space-1-5)",
              padding: "0 0 var(--space-2)",
            }}
          >
            {activePowerUps.map((pu) => (
              <motion.button
                key={pu.id}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onPowerUpToggle?.(pu.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-1)",
                  padding: "var(--space-1) var(--space-2-5)",
                  borderRadius: "var(--radius-pill)",
                  border: `1px solid ${pu.color}40`,
                  background: pu.colorSoft,
                  color: pu.color,
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  fontFamily: "var(--font-body)",
                  cursor: "pointer",
                  transition: "all var(--duration-fast) var(--ease-standard)",
                }}
              >
                {pu.icon}
                {pu.label}
                <X size={12} style={{ opacity: 0.6 }} />
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main composer */}
      <div
        className="sakura-composer"
        data-focused={isFocused}
        style={{
          background: "var(--bg-elevated)",
          border: `1px solid ${isFocused ? "var(--accent)" : "var(--border-default)"}`,
          borderRadius: "var(--radius-2xl)",
          boxShadow: isFocused ? "var(--shadow-focus)" : "var(--shadow-sm)",
          padding: "var(--space-3) var(--space-4)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-2)",
          transition: "border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)",
        }}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            handleInput();
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Ask HINAA anything..."
          disabled={disabled}
          rows={1}
          style={{
            width: "100%",
            border: "none",
            outline: "none",
            background: "transparent",
            fontFamily: "var(--font-body)",
            fontSize: "var(--text-base)",
            color: "var(--text-primary)",
            resize: "none",
            lineHeight: "var(--leading-normal)",
            minHeight: "24px",
            maxHeight: "180px",
            overflow: "auto",
          }}
        />

        {/* Toolbar */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--space-2)",
        }}>
          {/* Left: Power-up chips */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-1)",
            flexWrap: "wrap",
            flex: 1,
            minWidth: 0,
          }}>
            {visiblePowerUps.map((pu) => (
              <PowerUpChip
                key={pu.id}
                powerUp={pu}
                onToggle={() => onPowerUpToggle?.(pu.id)}
              />
            ))}
            {powerUps.length > 4 && (
              <button
                onClick={() => setShowAllPowerUps(!showAllPowerUps)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "var(--space-1) var(--space-2)",
                  borderRadius: "var(--radius-pill)",
                  border: "1px dashed var(--border-default)",
                  background: "transparent",
                  color: "var(--text-tertiary)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 500,
                  fontFamily: "var(--font-body)",
                  cursor: "pointer",
                }}
              >
                +{powerUps.length - 4}
              </button>
            )}
          </div>

          {/* Right: Action buttons */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-1-5)",
            flexShrink: 0,
          }}>
            {/* Attach */}
            <ComposerIconBtn title="Attach file" disabled={disabled}>
              <Paperclip size={16} />
            </ComposerIconBtn>

            {/* Voice */}
            {onVoiceToggle && (
              <ComposerIconBtn
                title={isVoiceActive ? "Stop voice" : "Start voice"}
                onClick={onVoiceToggle}
                active={isVoiceActive}
                disabled={disabled}
              >
                <Mic size={16} />
              </ComposerIconBtn>
            )}

            {/* Send / Stop */}
            {isGenerating ? (
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={onStop}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: "var(--danger)",
                  color: "white",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
                title="Stop generating"
                aria-label="Stop generating"
              >
                <StopCircle size={16} />
              </motion.button>
            ) : (
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={onSend}
                disabled={!value.trim() || disabled}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: value.trim() ? "var(--accent)" : "var(--border-subtle)",
                  color: value.trim() ? "white" : "var(--text-tertiary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: value.trim() ? "pointer" : "not-allowed",
                  transition: "background var(--duration-fast) var(--ease-standard)",
                  boxShadow: value.trim() ? "0 2px 8px var(--accent-glow)" : "none",
                }}
                title="Send message"
                aria-label="Send message"
              >
                <Send size={16} />
              </motion.button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PowerUpChip({
  powerUp,
  onToggle,
}: {
  powerUp: PowerUp;
  onToggle: () => void;
}) {
  return (
    <motion.button
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.96 }}
      onClick={onToggle}
      title={powerUp.label}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-1)",
        padding: "var(--space-1) var(--space-2)",
        borderRadius: "var(--radius-pill)",
        border: `1px solid ${powerUp.enabled ? powerUp.color + "40" : "var(--border-subtle)"}`,
        background: powerUp.enabled ? powerUp.colorSoft : "transparent",
        color: powerUp.enabled ? powerUp.color : "var(--text-tertiary)",
        fontSize: "var(--text-xs)",
        fontWeight: 500,
        fontFamily: "var(--font-body)",
        cursor: "pointer",
        transition: "all var(--duration-fast) var(--ease-standard)",
        whiteSpace: "nowrap",
      }}
      aria-pressed={powerUp.enabled}
    >
      {powerUp.icon}
      <span className="sakura-chip-label">{powerUp.label}</span>
    </motion.button>
  );
}

function ComposerIconBtn({
  children,
  title,
  onClick,
  active = false,
  disabled = false,
}: {
  children: React.ReactNode;
  title: string;
  onClick?: () => void;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      style={{
        width: 32,
        height: 32,
        borderRadius: "var(--radius-sm)",
        border: `1px solid ${active ? "var(--accent)" : "var(--border-subtle)"}`,
        background: active ? "var(--accent-pale)" : "transparent",
        color: active ? "var(--accent)" : "var(--text-tertiary)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all var(--duration-fast) var(--ease-standard)",
      }}
    >
      {children}
    </button>
  );
}
