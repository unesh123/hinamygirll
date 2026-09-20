import React, { useState, useRef, useCallback, useEffect, type KeyboardEvent, type ChangeEvent } from "react";
import {
  Send,
  Paperclip,
  ArrowUp,
  Mic,
  Plus,
  Globe,
  Sparkles,
  Code,
  Square,
  X,
  Target,
  MessageSquare,
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
  Terminal,
  Zap,
  Music,
  Video,
  Camera,
  Link,
  Layout,
  Network,
} from "lucide-react";
import { ModelSelectorV7 } from "./ModelSelectorV7";
import type { DiscoveredModel, DiscoveredProvider } from "../../features/providers/hooks/useCapabilities";

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
  onSend: (options?: {
    mode?: ActionMode;
    intelligence?: IntelligenceLevel;
    attachmentRole?: AttachmentRole;
    isGoalMode?: boolean;
  }) => void;
  onStop?: () => void;
  isGenerating?: boolean;
  disabled?: boolean;
  isVoiceActive?: boolean;
  onVoiceToggle?: () => void;
  // Context Chips V2
  contextChips?: ContextChip[];
  onRemoveChip?: (id: string) => void;
  onAddChip?: (chip: ContextChip) => void;
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
  // Goal Mode
  isGoalMode?: boolean;
  onToggleGoalMode?: () => void;
  // Attachments
  attachedImage?: string | null;
  onImageAttach?: (dataUrl: string | null, role?: AttachmentRole) => void;
  // Smart + menu triggers
  onUploadFile?: (type?: string) => void;
  onSelectArtifact?: (type: string) => void;
  onAttachContext?: (type: string) => void;
  // Backend Capabilities & Real Models V7
  discoveredModels?: DiscoveredModel[];
  discoveredProviders?: DiscoveredProvider[];
  selectedModelId?: string | null;
  selectedProviderId?: string | null;
  isAutoRouter?: boolean;
  onSelectAuto?: () => void;
  onSelectModel?: (model: DiscoveredModel) => void;
  backendConnected?: boolean;
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
  onAddChip,
  activeTopic,
  onClearTopic,
  activeModel,
  activeProvider,
  onOpenModelSelector,
  intelligenceLevel = "auto",
  onChangeIntelligence,
  actionMode = "chat",
  onChangeActionMode,
  isGoalMode = false,
  onToggleGoalMode,
  attachedImage,
  onImageAttach,
  onUploadFile,
  onSelectArtifact,
  onAttachContext,
  discoveredModels = [],
  discoveredProviders = [],
  selectedModelId,
  selectedProviderId,
  isAutoRouter = true,
  onSelectAuto,
  onSelectModel,
  backendConnected = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedRole, setSelectedRole] = useState<AttachmentRole>("style_reference");
  const [showRoleMenu, setShowRoleMenu] = useState(false);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [showIntelMenu, setShowIntelMenu] = useState(false);
  const [showCreateMenu, setShowCreateMenu] = useState(false);
  const [previewChip, setPreviewChip] = useState<ContextChip | null>(null);

  // Footer status is measured from /v1/capabilities via props, never asserted:
  // the previous literals read "6 nodes online" green straight through an outage.
  const readyProviders = discoveredProviders.filter((p) => p.configured).length;
  const readyModels = discoveredModels.filter((m) => m.configured).length;
  const contextCount = contextChips.length + (attachedImage ? 1 : 0);
  const statusTone = !backendConnected
    ? { dot: "#ef4444", label: "Backend offline" }
    : readyProviders === 0
      ? { dot: "#f59e0b", label: "No providers configured" }
      : {
          dot: "#10b981",
          label: `${readyProviders} provider${readyProviders === 1 ? "" : "s"} · ${readyModels} models`,
        };

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

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowPlusMenu(false);
        setShowIntelMenu(false);
        setShowCreateMenu(false);
        setShowRoleMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isGenerating) {
        onStop?.();
      } else if (value.trim() || attachedImage) {
        onSend({
          mode: isGoalMode ? "goal" : actionMode,
          intelligence: intelligenceLevel,
          attachmentRole: selectedRole,
          isGoalMode,
        });
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
      case "repo":
        return <Globe size={12} />;
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

  const placeholderText = isGoalMode
    ? "Define your goal, constraints, and success criteria for Hina..."
    : actionMode === "research"
    ? "Ask a question to research with live web sources & citations..."
    : actionMode === "create"
    ? "Describe the website, document, presentation, or code to create..."
    : "Ask HINA anything — chat mode...";

  return (
    <div
      ref={containerRef}
      className="composer-v6"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "12px 14px",
        background: "var(--surface-card, #ffffff)",
        border: "1px solid var(--border-default, rgba(0, 0, 0, 0.1))",
        borderRadius: "var(--radius-lg, 16px)",
        boxShadow: "var(--shadow-card, 0 2px 8px -2px rgba(0,0,0,0.05))",
        transition: "border-color 0.15s ease, box-shadow 0.15s ease",
        position: "relative",
      }}
    >
      {/* ── Top Bar: Context Chips V2 [Project: HINAA x] [Repo: frontend x] [IMG_24 x] ─────────────────────── */}
      {allChips.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", paddingBottom: 2 }}>
          {allChips.map((chip) => (
            <div
              key={chip.id}
              data-testid={`context-chip-${chip.id}`}
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
                transition: "all 0.15s ease",
              }}
              onClick={() => setPreviewChip(previewChip?.id === chip.id ? null : chip)}
              title={chip.metadata || "Click to preview context"}
            >
              <span style={{ color: "var(--accent-primary, #dc5f8b)" }}>{getChipIcon(chip.type)}</span>
              <span style={{ maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {chip.label}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (chip.id === "active-topic") onClearTopic?.();
                  else onRemoveChip?.(chip.id);
                }}
                aria-label={`Remove ${chip.label}`}
                style={{
                  background: "none",
                  border: "none",
                  padding: 1,
                  display: "flex",
                  alignItems: "center",
                  cursor: "pointer",
                  color: "var(--text-tertiary, #847a83)",
                }}
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

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
                  boxShadow: "var(--shadow-dropdown, 0 10px 25px -5px rgba(0,0,0,0.1))",
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
        data-testid="composer-input"
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
          minHeight: 38,
          maxHeight: 200,
          padding: "2px 0",
        }}
      />

      {/* ── Bottom Controls: Signature Executive Layout ───────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
          paddingTop: 8,
          borderTop: "1px solid #f1f5f9",
        }}
      >
        {/* Left cluster: Badges [🔴 Command Center] [📎 N attached] [status from /v1/capabilities] */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div
            data-testid="badge-command-center"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "3px 8px",
              borderRadius: 6,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              fontSize: 11,
              fontWeight: 500,
              color: "#475569",
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#ef4444" }} />
            <span>Command Center</span>
          </div>

          {contextCount > 0 && (
            <div
              data-testid="badge-sources"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 8px",
                borderRadius: 6,
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
                fontSize: 11,
                fontWeight: 500,
                color: "#475569",
              }}
            >
              <Paperclip size={11} style={{ color: "#64748b" }} />
              <span>{contextCount} attached</span>
            </div>
          )}

          <div
            data-testid="badge-nodes-online"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "3px 8px",
              borderRadius: 6,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              fontSize: 11,
              fontWeight: 500,
              color: "#475569",
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusTone.dot }} />
            <span>{statusTone.label}</span>
          </div>
          {/* 1. `+` Menu Button */}
          <div style={{ position: "relative" }}>
            <button
              type="button"
              data-testid="composer-plus-btn"
              onClick={() => {
                setShowPlusMenu(!showPlusMenu);
                setShowIntelMenu(false);
                setShowCreateMenu(false);
              }}
              title="Attach, Upload, or Integrate"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: showPlusMenu ? "var(--surface-active, #ece7ed)" : "var(--surface-subtle, #f6f3f7)",
                border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                color: "var(--text-secondary, #5e545d)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <Plus size={15} />
            </button>

            {/* Smart Plus Menu Dropdown (4 Categories: Files & Media, Attach Context, Create, Integrations) */}
            {showPlusMenu && (
              <div
                style={{
                  position: "absolute",
                  bottom: "calc(100% + 8px)",
                  left: 0,
                  width: 240,
                  maxHeight: 360,
                  overflowY: "auto",
                  padding: 6,
                  background: "var(--surface-overlay, #ffffff)",
                  borderRadius: "var(--radius-md, 12px)",
                  boxShadow: "var(--shadow-dropdown, 0 10px 25px -5px rgba(0,0,0,0.1))",
                  border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
                  zIndex: 60,
                }}
              >
                {/* 1. Files & Media */}
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary, #847a83)", padding: "4px 8px" }}>
                  FILES & MEDIA
                </div>
                {[
                  { label: "Upload Image", icon: ImageIcon, action: () => fileInputRef.current?.click() },
                  { label: "Upload Audio", icon: Music, action: () => onUploadFile?.("audio") },
                  { label: "Upload Document", icon: FileText, action: () => onUploadFile?.("document") },
                  { label: "Upload Video", icon: Video, action: () => onUploadFile?.("video") },
                  { label: "Take Photo", icon: Camera, action: () => onUploadFile?.("camera") },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      item.action();
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
                      color: "var(--text-primary, #1e191d)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <item.icon size={13} style={{ color: "var(--accent-primary, #dc5f8b)" }} />
                    <span>{item.label}</span>
                  </button>
                ))}

                {/* 2. Attach Context */}
                <div style={{ height: 1, background: "var(--border-subtle, rgba(0,0,0,0.06))", margin: "4px 0" }} />
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary, #847a83)", padding: "4px 8px" }}>
                  ATTACH CONTEXT
                </div>
                {[
                  {
                    label: "Active Project",
                    icon: FolderGit2,
                    action: () =>
                      onAddChip?.({
                        id: `proj-${Date.now()}`,
                        type: "project",
                        label: "Project: HINAA",
                        metadata: "HINAA Autonomous Operating System",
                      }),
                  },
                  {
                    label: "GitHub Repo",
                    icon: Globe,
                    action: () =>
                      onAddChip?.({
                        id: `repo-${Date.now()}`,
                        type: "repo",
                        label: "Repo: frontend",
                        metadata: "apps/web codebase",
                      }),
                  },
                  {
                    label: "Paste URL",
                    icon: Link,
                    action: () => {
                      const url = window.prompt("Enter Context URL:");
                      if (url) {
                        onAddChip?.({
                          id: `url-${Date.now()}`,
                          type: "topic",
                          label: url.replace(/^https?:\/\//, "").slice(0, 20),
                          metadata: url,
                        });
                      }
                    },
                  },
                  {
                    label: "Live Canvas",
                    icon: Layout,
                    action: () =>
                      onAddChip?.({
                        id: `canvas-${Date.now()}`,
                        type: "artifact",
                        label: "Canvas: Active Locus",
                        metadata: "Real-time canvas context",
                      }),
                  },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      item.action();
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
                      color: "var(--text-primary, #1e191d)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <item.icon size={13} style={{ color: "#0ea5e9" }} />
                    <span>{item.label}</span>
                  </button>
                ))}

                {/* 3. Create */}
                <div style={{ height: 1, background: "var(--border-subtle, rgba(0,0,0,0.06))", margin: "4px 0" }} />
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary, #847a83)", padding: "4px 8px" }}>
                  CREATE
                </div>
                {[
                  { type: "website", label: "Website", icon: Globe },
                  { type: "document", label: "Document", icon: FileText },
                  { type: "presentation", label: "Presentation", icon: Tv },
                  { type: "spreadsheet", label: "Spreadsheet", icon: FileSpreadsheet },
                  { type: "image", label: "Image", icon: ImageIcon },
                  { type: "video", label: "Video", icon: Video },
                  { type: "code", label: "Code", icon: Code },
                  { type: "diagram", label: "Diagram", icon: Network },
                  { type: "analysis", label: "Analysis", icon: Terminal },
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
                      color: "var(--text-primary, #1e191d)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <item.icon size={13} style={{ color: "var(--accent-primary, #dc5f8b)" }} />
                    <span>{item.label}</span>
                  </button>
                ))}

                {/* 4. Integrations */}
                <div style={{ height: 1, background: "var(--border-subtle, rgba(0,0,0,0.06))", margin: "4px 0" }} />
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary, #847a83)", padding: "4px 8px" }}>
                  INTEGRATIONS
                </div>
                {[
                  { label: "Google Drive", icon: FolderGit2 },
                  { label: "Notion", icon: FileText },
                  { label: "GitHub", icon: Globe },
                  { label: "Slack", icon: MessageSquare },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      onAddChip?.({
                        id: `integ-${Date.now()}`,
                        type: "artifact",
                        label: item.label,
                        metadata: `${item.label} integration sync`,
                      });
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
                      color: "var(--text-primary, #1e191d)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <item.icon size={13} style={{ color: "#10b981" }} />
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

          {/* 2. `Auto ▾` Real Model / Intelligence Selector V7 */}
          <ModelSelectorV7
            models={discoveredModels}
            providers={discoveredProviders}
            selectedModelId={selectedModelId}
            selectedProviderId={selectedProviderId}
            isAutoRouter={isAutoRouter}
            onSelectAuto={() => {
              onSelectAuto?.();
              onChangeIntelligence?.("auto");
            }}
            onSelectModel={(model) => {
              onSelectModel?.(model);
            }}
            backendConnected={backendConnected}
          />

          {/* 3. `Goal Mode` Toggle Button */}
          <button
            type="button"
            data-testid="composer-goal-btn"
            aria-pressed={isGoalMode}
            onClick={onToggleGoalMode}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "4px 9px",
              borderRadius: "var(--radius-full, 9999px)",
              background: isGoalMode ? "rgba(220, 95, 139, 0.15)" : "var(--surface-subtle, #f6f3f7)",
              border: isGoalMode ? "1px solid var(--accent-primary, #dc5f8b)" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
              color: isGoalMode ? "var(--accent-primary, #dc5f8b)" : "var(--text-secondary, #5e545d)",
              fontSize: 11,
              fontWeight: isGoalMode ? 700 : 500,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            title="Toggle Autonomous Goal Mode"
          >
            <Target size={12} />
            <span>Goal Mode</span>
          </button>

          {/* 4. `Create ▾` Dropdown */}
          <div style={{ position: "relative" }}>
            <button
              type="button"
              data-testid="composer-create-btn"
              onClick={() => {
                setShowCreateMenu(!showCreateMenu);
                setShowPlusMenu(false);
                setShowIntelMenu(false);
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "4px 8px",
                borderRadius: "var(--radius-full, 9999px)",
                background: "var(--surface-subtle, #f6f3f7)",
                border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                fontSize: 11,
                fontWeight: 500,
                color: "var(--text-secondary, #5e545d)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
              title="Create Artifacts & Deliverables"
            >
              <Sparkles size={11} style={{ color: "var(--accent-primary, #dc5f8b)" }} />
              <span>Create</span>
              <ChevronDown size={10} style={{ opacity: 0.6 }} />
            </button>

            {showCreateMenu && (
              <div
                style={{
                  position: "absolute",
                  bottom: "calc(100% + 8px)",
                  left: 0,
                  width: 180,
                  padding: 4,
                  background: "var(--surface-overlay, #ffffff)",
                  borderRadius: "var(--radius-md, 12px)",
                  boxShadow: "var(--shadow-dropdown, 0 10px 25px -5px rgba(0,0,0,0.1))",
                  border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
                  zIndex: 60,
                }}
              >
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary)", padding: "4px 8px" }}>
                  CREATE ARTIFACT
                </div>
                {[
                  { type: "website", label: "Website", icon: Globe },
                  { type: "document", label: "Document", icon: FileText },
                  { type: "presentation", label: "Presentation", icon: Tv },
                  { type: "spreadsheet", label: "Spreadsheet", icon: FileSpreadsheet },
                  { type: "image", label: "Image", icon: ImageIcon },
                  { type: "video", label: "Video", icon: Video },
                  { type: "code", label: "Code", icon: Code },
                  { type: "diagram", label: "Diagram", icon: Network },
                  { type: "analysis", label: "Analysis", icon: Terminal },
                ].map((item) => (
                  <button
                    key={item.type}
                    type="button"
                    onClick={() => {
                      onSelectArtifact?.(item.type);
                      setShowCreateMenu(false);
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
                    <item.icon size={13} style={{ color: "var(--accent-primary, #dc5f8b)" }} />
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Right cluster of controls: Shortcuts + 🎙 Voice & ↑ Send */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="composer-v6__shortcuts" style={{ fontSize: 11, color: "#94a3b8" }}>
            <span>send ↵</span>
            <span>newline ⇧↵</span>
          </div>
          {onVoiceToggle && (
            <button
              type="button"
              data-testid="composer-voice-btn"
              onClick={onVoiceToggle}
              title={isVoiceActive ? "Mute Voice" : "Enable Real-time Voice"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: isVoiceActive ? "var(--accent-subtle, rgba(220, 95, 139, 0.15))" : "var(--surface-subtle, #f6f3f7)",
                border: isVoiceActive ? "1px solid var(--accent-primary, #dc5f8b)" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                color: isVoiceActive ? "var(--accent-primary, #dc5f8b)" : "var(--text-secondary, #5e545d)",
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
              data-testid="composer-send-btn"
              onClick={() =>
                onSend({
                  mode: isGoalMode ? "goal" : actionMode,
                  intelligence: intelligenceLevel,
                  attachmentRole: selectedRole,
                  isGoalMode,
                })
              }
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
                  !value.trim() && !attachedImage ? "#f1f5f9" : "#1a232b",
                color: !value.trim() && !attachedImage ? "var(--text-muted, #a198a0)" : "#ffffff",
                border: "none",
                cursor: !value.trim() && !attachedImage ? "not-allowed" : "pointer",
                boxShadow: !value.trim() && !attachedImage ? "none" : "var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.1))",
                transition: "all 0.15s ease",
              }}
            >
              <ArrowUp size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
