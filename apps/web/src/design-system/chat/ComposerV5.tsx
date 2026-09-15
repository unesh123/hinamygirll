import { useState, useRef, useCallback, useEffect, type KeyboardEvent, type ChangeEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Mic,
  Paperclip,
  Globe,
  Sparkles,
  Code,
  Square,
  X,
  Target,
  MessageSquare,
  Brain,
  ChevronDown,
  User,
  Palette,
  Eye,
} from "lucide-react";

export type ActionMode = "chat" | "research" | "create" | "code";
export type AttachmentRole = "face_reference" | "style_reference" | "inspection";

export interface ComposerV5Props {
  value: string;
  onChange: (value: string) => void;
  onSend: (mode?: ActionMode, attachmentRole?: AttachmentRole) => void;
  onStop?: () => void;
  isGenerating?: boolean;
  disabled?: boolean;
  isVoiceActive?: boolean;
  onVoiceToggle?: () => void;
  // Context Chips
  activeTopic?: string | null;
  onClearTopic?: () => void;
  activeModel?: string | null;
  activeProvider?: string | null;
  onOpenModelSelector?: () => void;
  // Goal Mode
  goalModeEnabled?: boolean;
  onToggleGoalMode?: () => void;
  // Action Mode
  actionMode?: ActionMode;
  onChangeActionMode?: (mode: ActionMode) => void;
  // Attachments
  attachedImage?: string | null;
  onImageAttach?: (dataUrl: string | null, role?: AttachmentRole) => void;
}

export function ComposerV5({
  value,
  onChange,
  onSend,
  onStop,
  isGenerating = false,
  disabled = false,
  isVoiceActive = false,
  onVoiceToggle,
  activeTopic,
  onClearTopic,
  activeModel,
  activeProvider,
  onOpenModelSelector,
  goalModeEnabled = false,
  onToggleGoalMode,
  actionMode = "chat",
  onChangeActionMode,
  attachedImage,
  onImageAttach,
}: ComposerV5Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedRole, setSelectedRole] = useState<AttachmentRole>("style_reference");
  const [showRoleMenu, setShowRoleMenu] = useState(false);

  // Auto-grow textarea
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isGenerating) {
        onStop?.();
      } else if (value.trim() || attachedImage) {
        onSend(actionMode, selectedRole);
      }
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      onImageAttach?.(reader.result as string, selectedRole);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (e.clipboardData && e.clipboardData.items) {
      const items = e.clipboardData.items;
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith("image/")) {
          const file = items[i].getAsFile();
          if (file) {
            const reader = new FileReader();
            reader.onload = () => {
              if (typeof reader.result === "string") {
                onImageAttach?.(reader.result, selectedRole);
              }
            };
            reader.readAsDataURL(file);
            e.preventDefault();
            break;
          }
        }
      }
    }
  };

  const placeholderText =
    actionMode === "research"
      ? "Ask a question to research with live web sources & citations..."
      : actionMode === "create"
      ? "Describe the image or document you want to create..."
      : actionMode === "code"
      ? "Describe code to write, test, or repair autonomously..."
      : "Ask HINAA anything...";

  return (
    <div
      data-testid="composer-v5"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "6px",
        width: "100%",
        padding: "8px 12px 10px",
        background: "var(--bg-surface)",
        borderTop: "1px solid var(--border-subtle)",
      }}
    >
      {/* ── Context Chips & Controls Row ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "6px",
        }}
      >
        {/* Left: Active Context Chips */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          {/* Active Topic Chip */}
          {activeTopic && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: "2px 8px",
                borderRadius: "12px",
                background: "var(--accent-pale, rgba(235, 111, 146, 0.12))",
                border: "1px solid var(--accent, #eb6f92)",
                fontSize: "0.72rem",
                color: "var(--accent, #eb6f92)",
                fontWeight: 600,
              }}
            >
              <span>📌 {activeTopic.length > 24 ? `${activeTopic.slice(0, 24)}...` : activeTopic}</span>
              {onClearTopic && (
                <button
                  type="button"
                  onClick={onClearTopic}
                  aria-label="Clear active thread topic"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: 0,
                    border: "none",
                    background: "none",
                    cursor: "pointer",
                    color: "inherit",
                  }}
                >
                  <X size={11} />
                </button>
              )}
            </motion.div>
          )}

          {/* Model / Brain Chip */}
          <button
            type="button"
            onClick={onOpenModelSelector}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "2px 8px",
              borderRadius: "12px",
              background: "var(--bg-surface-raised)",
              border: "1px solid var(--border-default)",
              fontSize: "0.72rem",
              color: "var(--text-secondary)",
              fontWeight: 500,
              cursor: onOpenModelSelector ? "pointer" : "default",
            }}
          >
            <Brain size={12} color="var(--accent)" />
            <span>{activeModel || activeProvider || "Brain: Auto"}</span>
          </button>

          {/* Goal Mode Toggle Pill */}
          <button
            type="button"
            data-testid="goal-mode-toggle"
            onClick={onToggleGoalMode}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "2px 10px",
              borderRadius: "12px",
              background: goalModeEnabled
                ? "rgba(16, 185, 129, 0.15)"
                : "var(--bg-surface-raised)",
              border: goalModeEnabled
                ? "1px solid var(--success, #10b981)"
                : "1px solid var(--border-default)",
              color: goalModeEnabled ? "var(--success, #10b981)" : "var(--text-tertiary)",
              fontSize: "0.72rem",
              fontWeight: 650,
              cursor: "pointer",
              transition: "all 150ms ease",
            }}
          >
            <Target size={12} color={goalModeEnabled ? "var(--success, #10b981)" : "currentColor"} />
            <span>Goal Mode{goalModeEnabled ? " ON" : ""}</span>
          </button>
        </div>

        {/* Right: Action Modes */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px",
            borderRadius: "14px",
            background: "var(--bg-surface-raised)",
            border: "1px solid var(--border-subtle)",
            gap: "2px",
          }}
        >
          {(
            [
              { id: "chat", label: "Chat", icon: <MessageSquare size={11} /> },
              { id: "research", label: "Research", icon: <Globe size={11} /> },
              { id: "create", label: "Create", icon: <Sparkles size={11} /> },
              { id: "code", label: "Code", icon: <Code size={11} /> },
            ] as const
          ).map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => onChangeActionMode?.(mode.id)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: "2px 8px",
                borderRadius: "10px",
                border: "none",
                background: actionMode === mode.id ? "var(--accent)" : "transparent",
                color: actionMode === mode.id ? "#ffffff" : "var(--text-secondary)",
                fontSize: "0.68rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 120ms ease",
              }}
            >
              {mode.icon}
              <span>{mode.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Smart Attachment Preview Bar ── */}
      {attachedImage && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "6px 10px",
            borderRadius: "var(--radius-md, 8px)",
            background: "var(--bg-surface-raised)",
            border: "1px solid var(--border-default)",
          }}
        >
          <img
            src={attachedImage}
            alt="Attached reference"
            style={{
              width: 36,
              height: 36,
              borderRadius: "4px",
              objectFit: "cover",
            }}
          />

          {/* Role selector dropdown */}
          <div style={{ position: "relative" }}>
            <button
              type="button"
              onClick={() => setShowRoleMenu((v) => !v)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "3px 8px",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
                background: "var(--bg-surface)",
                fontSize: "0.72rem",
                color: "var(--text-primary)",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              {selectedRole === "face_reference" ? (
                <>
                  <User size={12} color="var(--accent)" />
                  <span>Face Identity (Preserve)</span>
                </>
              ) : selectedRole === "style_reference" ? (
                <>
                  <Palette size={12} color="#3b82f6" />
                  <span>Style Reference</span>
                </>
              ) : (
                <>
                  <Eye size={12} color="#10b981" />
                  <span>Visual Inspection</span>
                </>
              )}
              <ChevronDown size={11} />
            </button>

            {showRoleMenu && (
              <div
                style={{
                  position: "absolute",
                  bottom: "100%",
                  left: 0,
                  marginBottom: "4px",
                  zIndex: 50,
                  background: "var(--bg-surface-raised)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "8px",
                  boxShadow: "0 6px 16px rgba(0,0,0,0.15)",
                  padding: "4px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                  minWidth: "160px",
                }}
              >
                {[
                  { role: "face_reference" as const, label: "Face Identity", desc: "Preserve exact face" },
                  { role: "style_reference" as const, label: "Style Reference", desc: "Match aesthetic & colors" },
                  { role: "inspection" as const, label: "Inspection", desc: "Analyze content" },
                ].map((item) => (
                  <button
                    key={item.role}
                    type="button"
                    onClick={() => {
                      setSelectedRole(item.role);
                      setShowRoleMenu(false);
                      onImageAttach?.(attachedImage, item.role);
                    }}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      border: "none",
                      background: selectedRole === item.role ? "var(--accent-pale)" : "transparent",
                      color: selectedRole === item.role ? "var(--accent)" : "var(--text-primary)",
                      fontSize: "0.72rem",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>{item.label}</span>
                    <span style={{ fontSize: "0.65rem", color: "var(--text-tertiary)" }}>{item.desc}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => onImageAttach?.(null)}
            aria-label="Remove image attachment"
            style={{
              marginLeft: "auto",
              padding: "4px",
              border: "none",
              background: "none",
              color: "var(--danger-text, #ef4444)",
              cursor: "pointer",
            }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* ── Main Textarea Container ── */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: "8px",
          padding: "6px 10px",
          background: "var(--bg-surface-raised)",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-xl, 14px)",
          boxShadow: "var(--shadow-sm)",
          transition: "border-color 150ms ease, box-shadow 150ms ease",
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />

        {/* Attach file button */}
        <button
          type="button"
          aria-label="Attach reference image"
          onClick={() => fileInputRef.current?.click()}
          style={{
            flexShrink: 0,
            width: 32,
            height: 32,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "6px",
            border: "none",
            background: attachedImage ? "var(--accent-pale)" : "transparent",
            color: attachedImage ? "var(--accent)" : "var(--text-tertiary)",
            cursor: "pointer",
          }}
        >
          <Paperclip size={16} />
        </button>

        {/* Main Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={placeholderText}
          aria-label="Composer input"
          rows={1}
          disabled={disabled}
          data-testid="chat-input"
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            color: "var(--text-primary)",
            fontSize: "0.95rem",
            fontFamily: "var(--font-body, system-ui, sans-serif)",
            lineHeight: "1.5",
            resize: "none",
            maxHeight: 180,
            padding: "4px 0",
          }}
        />

        {/* Voice button */}
        {onVoiceToggle && (
          <button
            type="button"
            onClick={onVoiceToggle}
            aria-label={isVoiceActive ? "Stop voice" : "Start voice"}
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "6px",
              border: "none",
              background: isVoiceActive ? "var(--danger-bg, rgba(239, 68, 68, 0.15))" : "transparent",
              color: isVoiceActive ? "var(--danger, #ef4444)" : "var(--text-tertiary)",
              cursor: "pointer",
            }}
          >
            <Mic size={16} />
          </button>
        )}

        {/* Send / Stop button */}
        {isGenerating ? (
          <button
            type="button"
            onClick={onStop}
            title="Stop generation"
            aria-label="Stop generation"
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "6px",
              border: "none",
              background: "var(--danger-bg, rgba(239, 68, 68, 0.15))",
              color: "var(--danger, #ef4444)",
              cursor: "pointer",
            }}
          >
            <Square size={14} fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onSend(actionMode, selectedRole)}
            disabled={!value.trim() && !attachedImage}
            title="Send"
            aria-label="Send message"
            data-testid="send-button"
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "6px",
              border: "none",
              background: value.trim() || attachedImage ? "var(--accent)" : "var(--bg-subtle)",
              color: value.trim() || attachedImage ? "#ffffff" : "var(--text-disabled)",
              cursor: value.trim() || attachedImage ? "pointer" : "default",
              transition: "background 150ms ease",
            }}
          >
            <Send size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
