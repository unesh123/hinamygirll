import React, { useState, useRef, useCallback, useEffect, type KeyboardEvent, type ChangeEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Mic,
  Plus,
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
  FileText,
  FolderGit2,
  Image as ImageIcon,
  CheckCircle2,
  FileSpreadsheet,
  Tv,
  HelpCircle,
  Terminal,
  Zap,
} from "lucide-react";

export type ActionMode = "chat" | "research" | "create" | "code" | "goal";
export type IntelligenceLevel = "auto" | "fast" | "deep" | "max";
export type AttachmentRole = "face_reference" | "style_reference" | "inspection";

export interface ContextChip {
  id: string;
  type: "project" | "repo" | "file" | "image" | "artifact" | "task" | "goal" | "topic";
  label: string;
  metadata?: string;
  previewContent?: string;
}

export interface ComposerV6Props {
  value: string;
  onChange: (value: string) => void;
  onSend: (options?: { mode?: ActionMode; intelligence?: IntelligenceLevel; attachmentRole?: AttachmentRole }) => void;
  onStop?: () => void;
  isGenerating?: boolean;
  disabled?: boolean;
  isVoiceActive?: boolean;
  onVoiceToggle?: () => void;
  // Context Chips V2
  contextChips?: ContextChip[];
  onRemoveChip?: (id: string) => void;
  // Legacy aliases
  activeTopic?: string | null;
  onClearTopic?: () => void;
  activeModel?: string | null;
  activeProvider?: string | null;
  onOpenModelSelector?: () => void;
  // Intelligence
  intelligenceLevel?: IntelligenceLevel;
  onChangeIntelligence?: (level: IntelligenceLevel) => void;
  // Action Mode
  actionMode?: ActionMode;
  onChangeActionMode?: (mode: ActionMode) => void;
  // Attachments
  attachedImage?: string | null;
  onImageAttach?: (dataUrl: string | null, role?: AttachmentRole) => void;
  // Smart + menu triggers
  onUploadFile?: () => void;
  onSelectArtifact?: (type: string) => void;
}

export const ComposerV6: React.FC<ComposerV6Props> = ({
  value,
  onChange,
  onSend,
  onStop,
  isGenerating = false,
  disabled = false,
  isVoiceActive = false,
  onVoiceToggle,
  contextChips = [],
  onRemoveChip,
  activeTopic,
  onClearTopic,
  activeModel,
  activeProvider,
  onOpenModelSelector,
  intelligenceLevel = "auto",
  onChangeIntelligence,
  actionMode = "chat",
  onChangeActionMode,
  attachedImage,
  onImageAttach,
  onUploadFile,
  onSelectArtifact,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedRole, setSelectedRole] = useState<AttachmentRole>("style_reference");
  const [showRoleMenu, setShowRoleMenu] = useState(false);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [showIntelMenu, setShowIntelMenu] = useState(false);
  const [previewChip, setPreviewChip] = useState<ContextChip | null>(null);

  // Auto-grow textarea
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
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
        onSend({ mode: actionMode, intelligence: intelligenceLevel, attachmentRole: selectedRole });
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

  // Compile chips including legacy activeTopic
  const allChips: ContextChip[] = [...contextChips];
  if (activeTopic && !allChips.some((c) => c.type === "topic")) {
    allChips.unshift({
      id: "active-topic",
      type: "topic",
      label: activeTopic,
      metadata: "Active Thread Topic",
    });
  }

  const getChipIcon = (type: ContextChip["type"]) => {
    switch (type) {
      case "project":
        return <FolderGit2 size={12} />;
      case "file":
        return <FileText size={12} />;
      case "image":
        return <ImageIcon size={12} />;
      case "goal":
        return <Target size={12} />;
      case "artifact":
        return <Sparkles size={12} />;
      case "topic":
      default:
        return <MessageSquare size={12} />;
    }
  };

  const placeholderText =
    actionMode === "research"
      ? "Ask a question to research with live web sources & citations..."
      : actionMode === "create"
      ? "Describe the image, presentation, or document to create..."
      : actionMode === "code"
      ? "Describe code to write, test, or repair autonomously..."
      : actionMode === "goal"
      ? "Define an end goal with acceptance criteria and constraints..."
      : "Ask HINAA anything...";

  return (
    <div
      className="composer-v6"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "10px 14px",
        background: "var(--surface-card, #ffffff)",
        border: "1px solid var(--border-default, rgba(0, 0, 0, 0.1))",
        borderRadius: "var(--radius-lg, 16px)",
        boxShadow: "var(--shadow-card, 0 2px 8px -2px rgba(0,0,0,0.05))",
        transition: "border-color 0.15s ease, box-shadow 0.15s ease",
        position: "relative",
      }}
    >
      {/* ── Top Bar: Context Chips V2 & Mode Badges ─────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
        {/* Chips list */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          {allChips.map((chip) => (
            <div
              key={chip.id}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 8px",
                borderRadius: "var(--radius-full, 9999px)",
                background: "var(--surface-subtle, #f6f3f7)",
                border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                fontSize: 11,
                fontWeight: 500,
                color: "var(--text-secondary, #5e545d)",
                cursor: "pointer",
              }}
              onClick={() => setPreviewChip(previewChip?.id === chip.id ? null : chip)}
              title={chip.metadata || "Click to preview context"}
            >
              <span style={{ color: "var(--accent-primary, #dc5f8b)" }}>{getChipIcon(chip.type)}</span>
              <span style={{ maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {chip.label}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (chip.id === "active-topic") onClearTopic?.();
                  else onRemoveChip?.(chip.id);
                }}
                style={{
                  background: "none",
                  border: "none",
                  padding: 1,
                  display: "flex",
                  alignItems: "center",
                  cursor: "pointer",
                  color: "var(--text-tertiary)",
                }}
              >
                <X size={11} />
              </button>
            </div>
          ))}

          {/* Action Modes Selector */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 2,
              padding: 2,
              borderRadius: "var(--radius-full, 9999px)",
              background: "var(--surface-subtle, #f6f3f7)",
              border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
            }}
          >
            {(
              [
                { mode: "chat", label: "Chat", icon: MessageSquare },
                { mode: "research", label: "Research", icon: Globe },
                { mode: "create", label: "Create", icon: Sparkles },
                { mode: "code", label: "Code", icon: Code },
                { mode: "goal", label: "Goal", icon: Target },
              ] as const
            ).map((item) => {
              const active = actionMode === item.mode;
              const IconComp = item.icon;
              return (
                <button
                  key={item.mode}
                  type="button"
                  onClick={() => onChangeActionMode?.(item.mode)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "3px 8px",
                    borderRadius: "var(--radius-full, 9999px)",
                    border: "none",
                    background: active ? "var(--surface-card, #ffffff)" : "transparent",
                    color: active ? "var(--accent-primary, #dc5f8b)" : "var(--text-tertiary, #847a83)",
                    boxShadow: active ? "var(--shadow-sm)" : "none",
                    fontSize: 11,
                    fontWeight: active ? 600 : 500,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  <IconComp size={11} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right side: Intelligence level badge */}
        <div style={{ position: "relative" }}>
          <button
            type="button"
            onClick={() => setShowIntelMenu(!showIntelMenu)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "3px 9px",
              borderRadius: "var(--radius-full, 9999px)",
              background: "var(--surface-subtle, #f6f3f7)",
              border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
              fontSize: 11,
              fontWeight: 600,
              color: intelligenceLevel === "auto" ? "var(--text-secondary)" : "var(--accent-primary)",
              cursor: "pointer",
            }}
            title="Intelligence Level Selector"
          >
            <Zap size={11} />
            <span style={{ textTransform: "capitalize" }}>{intelligenceLevel}</span>
            <ChevronDown size={10} style={{ opacity: 0.6 }} />
          </button>

          {showIntelMenu && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                right: 0,
                width: 160,
                padding: 4,
                background: "var(--surface-overlay, #ffffff)",
                borderRadius: "var(--radius-md, 12px)",
                boxShadow: "var(--shadow-dropdown, 0 10px 25px -5px rgba(0,0,0,0.1))",
                border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
                zIndex: 50,
              }}
            >
              {(["auto", "fast", "deep", "max"] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => {
                    onChangeIntelligence?.(lvl);
                    setShowIntelMenu(false);
                  }}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 8px)",
                    border: "none",
                    background: intelligenceLevel === lvl ? "var(--surface-subtle)" : "transparent",
                    color: intelligenceLevel === lvl ? "var(--accent-primary)" : "var(--text-primary)",
                    fontSize: 12,
                    fontWeight: intelligenceLevel === lvl ? 600 : 400,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <span style={{ textTransform: "capitalize" }}>{lvl}</span>
                  {intelligenceLevel === lvl && <CheckCircle2 size={12} />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Chip Preview Popover */}
      {previewChip && (
        <div
          style={{
            padding: "8px 12px",
            background: "var(--surface-subtle, #f6f3f7)",
            borderRadius: "var(--radius-sm, 8px)",
            border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
            fontSize: 12,
            color: "var(--text-secondary)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <strong style={{ color: "var(--text-primary)" }}>{previewChip.label}</strong> ({previewChip.type})
            {previewChip.previewContent && <div style={{ marginTop: 2 }}>{previewChip.previewContent}</div>}
          </div>
          <button
            onClick={() => setPreviewChip(null)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)" }}
          >
            <X size={13} />
          </button>
        </div>
      )}

      {/* ── Attachment Preview & Role Selection ──────────────────────────── */}
      {attachedImage && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 0" }}>
          <div style={{ position: "relative", width: 52, height: 52, borderRadius: 8, overflow: "hidden" }}>
            <img src={attachedImage} alt="Attachment" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            <button
              type="button"
              onClick={() => onImageAttach?.(null)}
              style={{
                position: "absolute",
                top: 2,
                right: 2,
                width: 18,
                height: 18,
                borderRadius: "50%",
                background: "rgba(0,0,0,0.65)",
                color: "#fff",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              <X size={11} />
            </button>
          </div>

          <div style={{ position: "relative" }}>
            <button
              type="button"
              onClick={() => setShowRoleMenu(!showRoleMenu)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "4px 10px",
                borderRadius: "var(--radius-full, 9999px)",
                background: "var(--surface-subtle)",
                border: "1px solid var(--border-default)",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
            >
              <span>
                Role: {selectedRole === "face_reference" ? "Face ID" : selectedRole === "style_reference" ? "Style" : "Inspect"}
              </span>
              <ChevronDown size={11} />
            </button>

            {showRoleMenu && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 4px)",
                  left: 0,
                  width: 170,
                  padding: 4,
                  background: "var(--surface-overlay, #ffffff)",
                  borderRadius: "var(--radius-md, 12px)",
                  boxShadow: "var(--shadow-dropdown)",
                  border: "1px solid var(--border-default)",
                  zIndex: 50,
                }}
              >
                {[
                  { role: "face_reference" as AttachmentRole, label: "Face Identity", icon: User },
                  { role: "style_reference" as AttachmentRole, label: "Style Reference", icon: Palette },
                  { role: "inspection" as AttachmentRole, label: "General Inspection", icon: Eye },
                ].map((item) => (
                  <button
                    key={item.role}
                    type="button"
                    onClick={() => {
                      setSelectedRole(item.role);
                      setShowRoleMenu(false);
                    }}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "6px 8px",
                      borderRadius: 6,
                      border: "none",
                      background: selectedRole === item.role ? "var(--surface-subtle)" : "transparent",
                      fontSize: 11,
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <item.icon size={12} />
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Main Textarea ─────────────────────────────────────────────────── */}
      <textarea
        ref={textareaRef}
        aria-label="Message HINAA"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        placeholder={placeholderText}
        disabled={disabled}
        rows={1}
        style={{
          width: "100%",
          resize: "none",
          background: "transparent",
          border: "none",
          outline: "none",
          fontSize: 14,
          lineHeight: "1.5",
          color: "var(--text-primary, #1e191d)",
          minHeight: 36,
          maxHeight: 200,
          padding: "2px 0",
        }}
      />

      {/* ── Bottom Controls: Smart Plus Menu, Voice, Send ───────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
        {/* Left: Smart `+` Menu */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, position: "relative" }}>
          <button
            type="button"
            onClick={() => setShowPlusMenu(!showPlusMenu)}
            title="Attach, Upload, or Create"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 30,
              height: 30,
              borderRadius: "50%",
              background: showPlusMenu ? "var(--surface-active)" : "var(--surface-subtle)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-secondary)",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <Plus size={15} />
          </button>

          {/* Smart Plus Menu Dropdown */}
          {showPlusMenu && (
            <div
              style={{
                position: "absolute",
                bottom: "calc(100% + 8px)",
                left: 0,
                width: 220,
                padding: 6,
                background: "var(--surface-overlay, #ffffff)",
                borderRadius: "var(--radius-md, 12px)",
                boxShadow: "var(--shadow-dropdown)",
                border: "1px solid var(--border-default)",
                zIndex: 50,
              }}
            >
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary)", padding: "4px 8px" }}>
                UPLOAD & ATTACH
              </div>
              <button
                type="button"
                onClick={() => {
                  fileInputRef.current?.click();
                  setShowPlusMenu(false);
                }}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 8px",
                  borderRadius: 6,
                  border: "none",
                  background: "transparent",
                  fontSize: 12,
                  color: "var(--text-primary)",
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                <ImageIcon size={14} style={{ color: "var(--accent-primary)" }} />
                <span>Upload Image</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  onUploadFile?.();
                  setShowPlusMenu(false);
                }}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 8px",
                  borderRadius: 6,
                  border: "none",
                  background: "transparent",
                  fontSize: 12,
                  color: "var(--text-primary)",
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                <FileText size={14} style={{ color: "var(--accent-primary)" }} />
                <span>Upload Document / Code</span>
              </button>

              <div style={{ height: 1, background: "var(--border-subtle)", margin: "4px 0" }} />
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary)", padding: "4px 8px" }}>
                CREATE
              </div>
              {[
                { type: "image", label: "Image Studio", icon: ImageIcon },
                { type: "document", label: "Document / Report", icon: FileText },
                { type: "presentation", label: "Presentation Deck", icon: Tv },
                { type: "code", label: "Autorepair Coding Run", icon: Terminal },
              ].map((item) => (
                <button
                  key={item.type}
                  type="button"
                  onClick={() => {
                    onSelectArtifact?.(item.type);
                    setShowPlusMenu(false);
                  }}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "6px 8px",
                    borderRadius: 6,
                    border: "none",
                    background: "transparent",
                    fontSize: 12,
                    color: "var(--text-primary)",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <item.icon size={14} style={{ color: "var(--accent-primary)" }} />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
        </div>

        {/* Right: Voice Toggle & Send Button */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {onVoiceToggle && (
            <button
              type="button"
              onClick={onVoiceToggle}
              title={isVoiceActive ? "Mute Voice" : "Enable Real-time Voice"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: isVoiceActive ? "var(--accent-subtle)" : "var(--surface-subtle)",
                border: isVoiceActive ? "1px solid var(--accent-primary)" : "1px solid var(--border-subtle)",
                color: isVoiceActive ? "var(--accent-primary)" : "var(--text-secondary)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <Mic size={15} />
            </button>
          )}

          {isGenerating ? (
            <button
              type="button"
              onClick={onStop}
              title="Stop Generation"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "var(--semantic-danger-fg, #b91c1c)",
                color: "#ffffff",
                border: "none",
                cursor: "pointer",
              }}
            >
              <Square size={13} fill="currentColor" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onSend({ mode: actionMode, intelligence: intelligenceLevel, attachmentRole: selectedRole })}
              disabled={disabled || (!value.trim() && !attachedImage)}
              title="Send Message (Enter)"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background:
                  !value.trim() && !attachedImage
                    ? "var(--surface-subtle)"
                    : "var(--accent-primary, #dc5f8b)",
                color: !value.trim() && !attachedImage ? "var(--text-muted)" : "#ffffff",
                border: "none",
                cursor: !value.trim() && !attachedImage ? "not-allowed" : "pointer",
                boxShadow: !value.trim() && !attachedImage ? "none" : "var(--shadow-sm)",
                transition: "all 0.15s ease",
              }}
            >
              <Send size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
