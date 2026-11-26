import React, { useState, useRef, useCallback, useEffect, type KeyboardEvent, type ChangeEvent } from "react";
import {
  Send,
  Paperclip,
  ArrowUp,
  Mic,
  Plus,
  Globe,
  Sparkles,
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
  Tv,
  Terminal,
  Zap,
  Layout,
  Headphones,
  Loader2,
} from "lucide-react";
import { ModelSelectorV7 } from "./ModelSelectorV7";
import { ShapeshiftCard } from "../../features/chat/components/ShapeshiftCard";
import type { DiscoveredModel, DiscoveredProvider } from "../../features/providers/hooks/useCapabilities";
import { useVoiceTyping } from "../../features/audio/useVoiceTyping";
import { playTypingSound, playSendSound } from "../../lib/uiSound";

export type ActionMode = "chat" | "research" | "create" | "code" | "goal";
export type IntelligenceLevel = "auto" | "fast" | "deep" | "max";
export type AttachmentRole = "face_reference" | "style_reference" | "inspection";

/** What an attached picture is for. `chip` fits the composer's compact toggle. */
export const ATTACHMENT_ROLES: Array<{
  role: AttachmentRole;
  label: string;
  chip: string;
  icon: typeof User;
}> = [
  { role: "face_reference", label: "Face Identity", chip: "Face ID", icon: User },
  { role: "style_reference", label: "Style Reference", chip: "Style", icon: Palette },
  { role: "inspection", label: "General Inspection", chip: "Inspect", icon: Eye },
];

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
    text?: string;
    attachedMedia?: Array<{
      name: string;
      kind: string;
      mimeType?: string;
      assetId?: string;
      dataUrl?: string;
      textExcerpt?: string;
      contactSheetDataUrl?: string;
    }>;
  }) => void;
  onStop?: () => void;
  isGenerating?: boolean;
  disabled?: boolean;
  isVoiceActive?: boolean;
  onVoiceToggle?: () => void;
  isLiveVisionActive?: boolean;
  onToggleLiveVision?: () => void;
  // Context Chips V2
  contextChips?: ContextChip[];
  onRemoveChip?: (id: string) => void;
  // Legacy aliases
  activeTopic?: string | null;
  onClearTopic?: () => void;
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
  // Smart + menu trigger
  onSelectArtifact?: (type: string) => void;
  // Backend Capabilities & Real Models V7
  discoveredModels?: DiscoveredModel[];
  discoveredProviders?: DiscoveredProvider[];
  selectedModelId?: string | null;
  selectedProviderId?: string | null;
  isAutoRouter?: boolean;
  onSelectAuto?: () => void;
  onSelectModel?: (model: DiscoveredModel) => void;
  backendConnected?: boolean;
  /**
   * Phone layout: drops the status badge row. Those three badges wrapped to two
   * lines and left a 393px screen with ~230px of visible transcript.
   */
  compact?: boolean;
  onTabAdopt?: () => boolean | void;
  onEscDismiss?: () => void;
  isDark?: boolean;
}

export const ComposerV6: React.FC<ComposerV6Props> = ({
  value,
  onChange,
  onSend,
  onStop,
  isGenerating = false,
  disabled = false,
  compact = false,
  isDark = false,
  isVoiceActive = false,
  onVoiceToggle,
  isLiveVisionActive = false,
  onToggleLiveVision,
  contextChips = [],
  onRemoveChip,
  activeTopic,
  onClearTopic,
  onOpenModelSelector,
  intelligenceLevel = "auto",
  onChangeIntelligence,
  actionMode = "chat",
  onChangeActionMode,
  isGoalMode = false,
  onToggleGoalMode,
  attachedImage,
  onImageAttach,
  onSelectArtifact,
  discoveredModels = [],
  discoveredProviders = [],
  selectedModelId,
  selectedProviderId,
  isAutoRouter = true,
  onSelectAuto,
  onSelectModel,
  backendConnected = false,
  onTabAdopt,
  onEscDismiss,
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
  const [dismissedShapeshiftInput, setDismissedShapeshiftInput] = useState<string>("");
  const [attachedDocuments, setAttachedDocuments] = useState<
    Array<{
      name: string;
      text: string;
      kind: string;
      charCount: number;
      assetId?: string;
      mimeType?: string;
      contactSheetDataUrl?: string;
      durationSec?: number;
      frameCount?: number;
    }>
  >([]);
  const [extraImages, setExtraImages] = useState<string[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isExtractingDoc, setIsExtractingDoc] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [sendHovered, setSendHovered] = useState(false);

  const voiceTyping = useVoiceTyping({
    onTranscript: useCallback((text: string, isFinal: boolean) => {
      if (isFinal) {
        onChange(value ? `${value.trim()} ${text}` : text);
      }
    }, [value, onChange]),
  });

  // Footer status is measured, never asserted. `configured` only proves a
  // credential exists, which is how this chip stayed green straight through a
  // gateway rejecting every call; `health` carries the outcome of the last live
  // call the backend actually made. Fallback-role gateways are excluded because
  // the selector never offers them — this chip answers how many brains he can
  // pick, and green answers "one of them just answered".
  const pickableBrains = discoveredProviders.filter(
    (p) => p.configured && p.role !== "fallback",
  );
  const measuredBrains = pickableBrains.filter((p) => p.health !== undefined);
  const liveBrains = measuredBrains.filter((p) => p.health === "healthy").length;
  const untestedBrains = measuredBrains.filter((p) => p.health === "untested").length;
  const readyModels = discoveredModels.filter((m) => m.configured).length;
  const contextCount = contextChips.length + (attachedImage ? 1 : 0) + extraImages.length + attachedDocuments.length;
  const statusTone = !backendConnected
    ? { dot: "#ef4444", label: "Backend offline" }
    : pickableBrains.length === 0
      ? { dot: "#f59e0b", label: "No providers configured" }
      : liveBrains > 0
        ? {
            dot: "#10b981",
            label: `${liveBrains} brain${liveBrains === 1 ? "" : "s"} live · ${readyModels} models`,
          }
        : measuredBrains.length === 0
          ? {
              // No health data at all: say "unverified", never green and never red.
              dot: "#64748b",
              label: `${pickableBrains.length} configured · health unverified`,
            }
          : untestedBrains === measuredBrains.length
            ? {
                dot: "#64748b",
                label: `${untestedBrains} configured · no live call yet`,
              }
            : {
                dot: "#ef4444",
                label: `${measuredBrains.length - untestedBrains} brains failed their last call`,
              };

  // Auto-grow textarea up to 6 lines (~144px)
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 144) + "px";
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
    if (e.key === "Tab") {
      if (onTabAdopt) {
        const adopted = onTabAdopt();
        if (adopted !== false) {
          e.preventDefault();
          return;
        }
      }
    }
    if (e.key === "Escape") {
      setShowPlusMenu(false);
      setShowIntelMenu(false);
      setShowCreateMenu(false);
      setShowRoleMenu(false);
      onEscDismiss?.();
    }
    if (e.key === "Enter" && !e.shiftKey) {
      if (typeof window !== "undefined" && typeof (window as any).__hinaaUnlockAudio === "function") {
        try { (window as any).__hinaaUnlockAudio(); } catch {}
      }
      e.preventDefault();
      if (value.trim() || attachedImage || extraImages.length > 0 || attachedDocuments.length > 0) {
        playSendSound();
        if (isGenerating) {
          onStop?.();
        }
        const attachedMediaPayload = [
          ...extraImages.map((url, idx) => ({
            name: `reference_image_${idx + 2}.png`,
            kind: "image",
            mimeType: "image/png",
            dataUrl: url,
          })),
          ...attachedDocuments.map((d) => ({
            name: d.name,
            kind: d.kind.toLowerCase(),
            mimeType: d.mimeType,
            assetId: d.assetId,
            textExcerpt: d.text,
            contactSheetDataUrl: d.contactSheetDataUrl,
          })),
        ];
        const inlineDocs = attachedDocuments.filter((d) => !d.assetId && d.kind !== "VIDEO" && d.text.trim());
        const docContext = inlineDocs
          .map((d) => `\n\n📄 [ATTACHED DOCUMENT: ${d.name} (${d.kind})]\n\`\`\`\n${d.text}\n\`\`\`\n`)
          .join("\n");
        const finalText = value.trim()
          ? (docContext ? `${value.trim()}\n${docContext}` : value.trim())
          : attachedDocuments.length > 0
            ? (docContext
                ? `Please analyze this attached document:\n${docContext}`
                : `Please inspect the attached files (${attachedDocuments.map((d) => d.name).join(", ")}).`)
            : undefined;
        setAttachedDocuments([]);
        setExtraImages([]);
        setUploadError(null);
        if (finalText !== undefined && finalText !== value.trim()) {
          onChange("");
        }
        onSend({
          text: finalText,
          mode: isGoalMode ? "goal" : actionMode,
          intelligence: intelligenceLevel,
          attachmentRole: selectedRole,
          isGoalMode,
          attachedMedia: attachedMediaPayload.length > 0 ? attachedMediaPayload : undefined,
        });
      } else if (isGenerating) {
        onStop?.();
      }
      return;
    }

    if (!["Shift", "Control", "Alt", "Meta", "CapsLock", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      playTypingSound(e.key);
    }
  };

  const ingestFile = async (file: File, primaryOccupied?: { value: boolean }) => {
    setUploadError(null);
    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    const isImage =
      file.type.startsWith("image/") ||
      ["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "avif"].includes(ext);
    if (isImage) {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(new Error("Could not read image"));
        reader.readAsDataURL(file);
      }).catch(() => "");
      if (!dataUrl) return;
      const alreadyHasPrimary = primaryOccupied ? primaryOccupied.value : Boolean(attachedImage);
      if (!alreadyHasPrimary && onImageAttach) {
        if (primaryOccupied) primaryOccupied.value = true;
        onImageAttach(dataUrl, selectedRole);
      } else {
        setExtraImages((prev) => [...prev, dataUrl].slice(0, 7));
      }
      return;
    }

    const isVideo =
      file.type.startsWith("video/") ||
      ["mp4", "mov", "webm", "mkv", "avi", "m4v", "mpeg", "mpg"].includes(ext);
    if (isVideo) {
      setIsExtractingDoc(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("num_frames", "6");
        const res = await fetch("/api/v1/media/inspect-video", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          setUploadError(String(errJson?.detail || errJson?.error || `Video inspection failed (${res.status})`));
          return;
        }
        const data = await res.json();
        setAttachedDocuments((prev) => [
          ...prev,
          {
            name: file.name,
            text: String(data?.summary || ""),
            kind: "VIDEO",
            charCount: String(data?.summary || "").length,
            assetId: typeof data?.asset_id === "string" ? data.asset_id : undefined,
            mimeType: file.type || "video/mp4",
            contactSheetDataUrl:
              typeof data?.contact_sheet_data_url === "string" ? data.contact_sheet_data_url : undefined,
            durationSec: typeof data?.metadata?.duration_seconds === "number" ? data.metadata.duration_seconds : undefined,
            frameCount: Array.isArray(data?.frames) ? data.frames.length : undefined,
          },
        ]);
      } catch (err) {
        console.error("Video inspection error:", err);
        setUploadError("Could not inspect video frames.");
      } finally {
        setIsExtractingDoc(false);
      }
      return;
    }

    // All documents, Markdown, archives, spreadsheets, and code files
    setIsExtractingDoc(true);
    try {
      const isPlain = [
        "txt", "md", "markdown", "mdx", "json", "csv", "tsv", "log", "yaml", "yml", "toml",
        "py", "js", "jsx", "ts", "tsx", "mjs", "html", "htm", "css", "scss", "sql", "go", "rs", "sh", "ps1", "xml",
      ].includes(ext);

      let docText = "";
      let assetId: string | undefined;

      const assetForm = new FormData();
      assetForm.append("file", file);
      const assetReq = fetch("/api/v1/assets", { method: "POST", body: assetForm })
        .then(async (r) => (r.ok ? r.json() : null))
        .catch(() => null);

      const extractReq = (async () => {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch("/api/v1/documents/extract", { method: "POST", body: formData }).catch(() => null);
        if (res && res.ok) {
          const data = await res.json();
          return String(data?.text || "");
        }
        if (isPlain) {
          return await file.text().catch(() => "");
        }
        return "";
      })();

      const [assetJson, extractedText] = await Promise.all([assetReq, extractReq]);
      assetId = typeof assetJson?.asset_id === "string" ? assetJson.asset_id : undefined;
      docText = extractedText || (isPlain ? await file.text().catch(() => "") : "");

      if (docText.trim() || assetId) {
        const newDoc = {
          name: file.name,
          text: docText,
          kind: ext.toUpperCase() || "DOC",
          charCount: docText.length,
          assetId,
          mimeType: file.type || "application/octet-stream",
        };
        setAttachedDocuments((prev) => [...prev, newDoc]);
      } else {
        setUploadError(`Could not extract readable content from ${file.name}.`);
      }
    } catch (err) {
      console.error("Document extraction error:", err);
      setUploadError(`Failed to attach ${file.name}.`);
    } finally {
      setIsExtractingDoc(false);
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).slice(0, 8);
    if (files.length === 0) return;
    const primaryOccupied = { value: Boolean(attachedImage) };
    for (const file of files) {
      await ingestFile(file, primaryOccupied);
    }
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    if (disabled) return;
    e.preventDefault();
    if (!isDragOver) setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    const files = Array.from(e.dataTransfer?.files ?? []).slice(0, 8);
    const primaryOccupied = { value: Boolean(attachedImage) };
    for (const file of files) {
      await ingestFile(file, primaryOccupied);
    }
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
            return;
          }
        }
      }
    }

    // Auto-detect massive text pastes (> 50,000 characters) and ingest as structured .txt attachment
    const pastedText = e.clipboardData?.getData("text/plain");
    if (pastedText && pastedText.length > 50000) {
      e.preventDefault();
      const firstLine = pastedText.trim().split("\n")[0].slice(0, 32).replace(/[^a-zA-Z0-9_-]/g, "_") || "pasted_text";
      const docName = `${firstLine}_${Date.now().toString().slice(-4)}.txt`;
      setAttachedDocuments((prev) => [
        ...prev,
        {
          name: docName,
          text: pastedText,
          kind: "TXT",
          charCount: pastedText.length,
        },
      ]);
      if (!value.trim()) {
        onChange(`Attached document: ${docName} (${pastedText.length.toLocaleString()} characters). Please analyze this content.`);
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

  const placeholderText = voiceTyping.isListening
    ? "Listening to voice dictation... speak into your microphone"
    : isGoalMode
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
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={(e) => void handleDrop(e)}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "12px 14px",
        background: isDark ? "rgba(255, 255, 255, 0.05)" : "var(--surface-card, #ffffff)",
        border: isDragOver
          ? "1.5px dashed #8b5cf6"
          : isDark
            ? "1px solid rgba(255, 255, 255, 0.12)"
            : "1px solid var(--border-default, rgba(0, 0, 0, 0.1))",
        backdropFilter: isDark ? "blur(20px)" : "none",
        WebkitBackdropFilter: isDark ? "blur(20px)" : "none",
        borderRadius: "var(--radius-lg, 16px)",
        boxShadow: isDragOver
          ? "0 0 24px rgba(139, 92, 246, 0.25)"
          : isDark ? "0 10px 40px -10px rgba(0, 0, 0, 0.5)" : "var(--shadow-card, 0 2px 8px -2px rgba(0,0,0,0.05))",
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

      {/* ── Upload Status / Error Banner ──────────────────────────────────── */}
      {uploadError && (
        <div
          role="alert"
          data-testid="composer-upload-error"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "6px 10px",
            borderRadius: 8,
            background: isDark ? "rgba(239,68,68,0.14)" : "#fef2f2",
            border: "1px solid rgba(239,68,68,0.3)",
            color: isDark ? "#fca5a5" : "#b91c1c",
            fontSize: 11.5,
          }}
        >
          <span>{uploadError}</span>
          <button type="button" onClick={() => setUploadError(null)} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}>
            <X size={12} />
          </button>
        </div>
      )}

      {/* ── Multi-File / Video Frame / Multi-Image Strip ───────────────────── */}
      {(extraImages.length > 0 || attachedDocuments.length > 0 || isExtractingDoc) && (
        <div data-testid="composer-media-strip" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, padding: "4px 0" }}>
          {extraImages.map((imgUrl, idx) => (
            <div key={`extra-img-${idx}`} style={{ position: "relative", width: 52, height: 52, borderRadius: 8, overflow: "hidden", border: "1px solid var(--border-default)" }}>
              <img src={imgUrl} alt={`Reference ${idx + 2}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              <button
                type="button"
                aria-label={`Remove reference image ${idx + 2}`}
                onClick={() => setExtraImages((prev) => prev.filter((_, i) => i !== idx))}
                style={{ position: "absolute", top: 2, right: 2, width: 18, height: 18, borderRadius: "50%", background: "rgba(0,0,0,0.65)", color: "#fff", border: "none", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}
              >
                <X size={11} />
              </button>
            </div>
          ))}
          {attachedDocuments.map((doc, idx) => (
            <div
              key={`doc-${idx}-${doc.name}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "4px 8px",
                borderRadius: 10,
                background: "var(--surface-subtle)",
                border: "1px solid var(--border-default)",
                maxWidth: 260,
              }}
            >
              {doc.contactSheetDataUrl ? (
                <img
                  src={doc.contactSheetDataUrl}
                  alt={`${doc.name} contact sheet`}
                  style={{ width: 56, height: 34, objectFit: "cover", borderRadius: 5, flexShrink: 0 }}
                />
              ) : (
                <FileText size={14} style={{ color: "var(--accent-primary, #dc5f8b)", flexShrink: 0 }} />
              )}
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 11.5, fontWeight: 650, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {doc.name}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
                  {doc.kind === "VIDEO"
                    ? `VIDEO${doc.durationSec ? ` · ${doc.durationSec.toFixed(1)}s` : ""}${doc.frameCount ? ` · ${doc.frameCount} frames` : ""}`
                    : `${doc.kind} · ${doc.charCount.toLocaleString()} chars`}
                </div>
              </div>
              <button
                type="button"
                aria-label={`Remove ${doc.name}`}
                onClick={() => setAttachedDocuments((prev) => prev.filter((_, i) => i !== idx))}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)", padding: 2 }}
              >
                <X size={12} />
              </button>
            </div>
          ))}
          {isExtractingDoc && (
            <span style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 600 }}>
              Inspecting attachment…
            </span>
          )}
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
                Role: {ATTACHMENT_ROLES.find((item) => item.role === selectedRole)?.chip}
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
                {ATTACHMENT_ROLES.map((item) => (
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

      {/* ── Shapeshift Morphing Composer Preview ────────────────────── */}
      {value.trim() && value.trim() !== dismissedShapeshiftInput && (
        <ShapeshiftCard
          input={value}
          isDark={isDark}
          onDismiss={() => setDismissedShapeshiftInput(value.trim())}
          onExecute={(actionText, executeImmediately) => {
            if (executeImmediately) {
              onChange(actionText);
              setTimeout(() => {
                onSend({
                  mode: isGoalMode ? "goal" : actionMode,
                  intelligence: intelligenceLevel,
                  attachmentRole: selectedRole,
                  isGoalMode,
                });
              }, 50);
            } else {
              onChange(actionText);
            }
          }}
        />
      )}

      {/* ── Main Textarea ─────────────────────────────────────────────────── */}
      {voiceTyping.isListening && (
        <div
          data-testid="composer-voice-typing-banner"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 10px",
            borderRadius: 8,
            background: isDark ? "rgba(236, 72, 153, 0.15)" : "rgba(236, 72, 153, 0.08)",
            border: isDark ? "1px solid rgba(236, 72, 153, 0.35)" : "1px solid rgba(236, 72, 153, 0.25)",
            fontSize: 12,
            color: "#ec4899",
            animation: "pulse 2s infinite ease-in-out",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#ec4899",
              boxShadow: "0 0 8px #ec4899",
              flexShrink: 0,
            }}
          />
          <span style={{ fontWeight: 650, flexShrink: 0 }}>Voice Typing:</span>
          <span
            style={{
              fontStyle: "italic",
              opacity: 0.95,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
            }}
          >
            {voiceTyping.interimTranscript || "Listening... speak into your microphone"}
          </span>
          <button
            type="button"
            onClick={() => voiceTyping.stopListening()}
            style={{
              background: "transparent",
              border: "none",
              color: "#ec4899",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 600,
              textDecoration: "underline",
              flexShrink: 0,
            }}
          >
            Done
          </button>
        </div>
      )}
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
          color: isDark ? "#ffffff" : "var(--text-primary, #1e191d)",
          minHeight: 38,
          maxHeight: 144,
          padding: "2px 0",
        }}
      />
      {value.length > 500 && (
        <div
          data-testid="composer-char-counter"
          style={{
            alignSelf: "flex-end",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
            color: value.length > 4000 ? "#f43f5e" : (isDark ? "#94a3b8" : "#64748b"),
            marginTop: -4,
          }}
        >
          {value.length.toLocaleString()} chars
        </div>
      )}

      {/* ── Bottom Controls: Signature Executive Layout ───────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: compact ? 8 : 12,
          // Compact: one 40px line. Wrapping here cost the phone 141px of transcript.
          flexWrap: compact ? "nowrap" : "wrap",
          paddingTop: 8,
          borderTop: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid #f1f5f9",
        }}
      >
        {/* Left cluster: Badges [🔴 Command Center] [📎 N attached] [status from /v1/capabilities] */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            // Stacking this cluster cost the phone a second toolbar row.
            flexWrap: compact ? "nowrap" : "wrap",
            minWidth: 0,
            overflowX: compact ? "auto" : undefined,
            scrollbarWidth: "none",
          }}
        >
          {!compact && (
            <>
          <button
            type="button"
            data-testid="badge-command-center"
            onClick={() => onToggleGoalMode?.()}
            title={isGoalMode ? "Always-On Agent Execution Active (click to return to Auto)" : "Command Center (click to toggle Always-On Agent Execution)"}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "3px 9px",
              borderRadius: 6,
              background: isGoalMode
                ? (isDark ? "rgba(43, 127, 255, 0.18)" : "rgba(220, 95, 139, 0.14)")
                : (isDark ? "rgba(255, 255, 255, 0.06)" : "var(--surface-subtle, #f8fafc)"),
              border: isGoalMode
                ? (isDark ? "1px solid rgba(43, 127, 255, 0.45)" : "1px solid rgba(220, 95, 139, 0.45)")
                : (isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid var(--border-subtle, #e2e8f0)"),
              fontSize: 11,
              fontWeight: 550,
              color: isGoalMode
                ? (isDark ? "#93c5fd" : "var(--accent-primary, #dc5f8b)")
                : (isDark ? "rgba(255, 255, 255, 0.7)" : "var(--text-secondary, #475569)"),
              cursor: onToggleGoalMode ? "pointer" : "default",
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: backendConnected ? (isGoalMode ? "#10b981" : (isDark ? "#2b7fff" : "var(--accent-primary, #dc5f8b)")) : "#ef4444",
                boxShadow: backendConnected ? (isDark ? "0 0 8px rgba(43, 127, 255, 0.5)" : "0 0 6px rgba(220, 95, 139, 0.4)") : "none",
              }}
            />
            <span>{isGoalMode ? "Command Center · Agent ON" : "Command Center"}</span>
          </button>

          {contextCount > 0 && (
            <div
              data-testid="badge-sources"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 9px",
                borderRadius: 6,
                background: isDark ? "rgba(255, 255, 255, 0.06)" : "var(--surface-subtle, #f8fafc)",
                border: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid var(--border-subtle, #e2e8f0)",
                fontSize: 11,
                fontWeight: 500,
                color: isDark ? "rgba(255, 255, 255, 0.7)" : "var(--text-secondary, #475569)",
              }}
            >
              <Paperclip size={11} style={{ color: isDark ? "rgba(255, 255, 255, 0.6)" : "#64748b" }} />
              <span>{contextCount} attached</span>
            </div>
          )}

          {statusTone.dot === "#ef4444" && (
            <div
              data-testid="badge-nodes-online"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 9px",
                borderRadius: 6,
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                fontSize: 11,
                fontWeight: 500,
                color: "#ef4444",
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#ef4444" }} />
              <span>{statusTone.label}</span>
            </div>
          )}
            </>
          )}
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
              title="Attach an image or start a deliverable"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: showPlusMenu
                  ? (isDark ? "rgba(255, 255, 255, 0.15)" : "var(--surface-active, #ece7ed)")
                  : (isDark ? "rgba(255, 255, 255, 0.08)" : "var(--surface-subtle, #f6f3f7)"),
                border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                color: isDark ? "#ffffff" : "var(--text-secondary, #5e545d)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <Plus size={15} />
            </button>

            {/* Smart Plus Menu Dropdown: the image attachment and the real deliverable commands */}
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
                {/* One attachment is real: the hidden input below accepts image/* and
                    the turn payload carries a single imageUrl. */}
                {[
                  { label: "Upload Image", icon: ImageIcon, action: () => {
                    if (fileInputRef.current) {
                      fileInputRef.current.accept = "image/*";
                      fileInputRef.current.multiple = true;
                      fileInputRef.current.click();
                    }
                  }},
                  { label: "Inspect Video Frames", icon: Sparkles, action: () => {
                    if (fileInputRef.current) {
                      fileInputRef.current.accept = "video/*,.mp4,.mov,.webm,.mkv,.avi,.m4v";
                      fileInputRef.current.multiple = false;
                      fileInputRef.current.click();
                    }
                  }},
                  { label: "Upload Document / PDF", icon: FileText, action: () => {
                    if (fileInputRef.current) {
                      fileInputRef.current.accept = ".pdf,.docx,.pptx,.xlsx,.zip,.md,.markdown,.mdx,.txt,.json,.csv,.tsv,.log,.yaml,.yml,.toml,.py,.js,.jsx,.ts,.tsx,.mjs,.html,.htm,.css,.scss,.sql,.go,.rs,.sh,.ps1,.xml";
                      fileInputRef.current.multiple = true;
                      fileInputRef.current.click();
                    }
                  }},
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

                {/* 2. Modes & Tools */}
                <div style={{ height: 1, background: "var(--border-subtle, rgba(0,0,0,0.06))", margin: "4px 0" }} />
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary, #847a83)", padding: "4px 8px" }}>
                  MODES & TOOLS
                </div>
                <button
                  type="button"
                  onClick={() => {
                    onToggleGoalMode?.();
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
                    background: isGoalMode ? "var(--surface-subtle)" : "transparent",
                    fontSize: 12,
                    color: isGoalMode ? "var(--accent-primary, #dc5f8b)" : "var(--text-primary, #1e191d)",
                    fontWeight: isGoalMode ? 700 : 500,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <Target size={13} style={{ color: "var(--accent-primary, #dc5f8b)" }} />
                  <span>{isGoalMode ? "Goal Mode (Active)" : "Autonomous Goal Mode"}</span>
                </button>
                {onToggleLiveVision && (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleLiveVision?.();
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
                      background: isLiveVisionActive ? "var(--surface-subtle)" : "transparent",
                      fontSize: 12,
                      color: isLiveVisionActive ? "#10b981" : "var(--text-primary, #1e191d)",
                      fontWeight: isLiveVisionActive ? 700 : 500,
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <Eye size={13} style={{ color: isLiveVisionActive ? "#10b981" : "var(--accent-primary, #dc5f8b)" }} />
                    <span>{isLiveVisionActive ? "Stop Live Eyes" : "Live Eyes (Screen Share)"}</span>
                  </button>
                )}

                {/* 3. Create */}
                <div style={{ height: 1, background: "var(--border-subtle, rgba(0,0,0,0.06))", margin: "4px 0" }} />
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary, #847a83)", padding: "4px 8px" }}>
                  CREATE
                </div>
                {[
                  { cmd: "/code", label: "Build & Execute", icon: FolderGit2 },
                  { cmd: "/video", label: "Motion MP4", icon: Zap },
                  { cmd: "/image", label: "Image", icon: ImageIcon },
                  { cmd: "/document", label: "Document", icon: FileText },
                  { cmd: "/presentation", label: "Presentation", icon: Tv },
                  { cmd: "/research", label: "Research", icon: Globe },
                  { cmd: "/analyze", label: "Analysis", icon: Terminal },
                  { cmd: "/plan", label: "Plan", icon: Layout },
                ].map((item) => (
                  <button
                    key={item.cmd}
                    type="button"
                    onClick={() => {
                      onSelectArtifact?.(item.cmd);
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
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,video/*,.mp4,.mov,.webm,.mkv,.avi,.m4v,.pdf,.docx,.pptx,.xlsx,.zip,.md,.markdown,.mdx,.txt,.json,.csv,.tsv,.log,.yaml,.yml,.toml,.py,.js,.jsx,.ts,.tsx,.mjs,.html,.htm,.css,.scss,.sql,.go,.rs,.sh,.ps1,.xml"
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
            placement="top"
            isDark={isDark}
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
              whiteSpace: "nowrap",
              flexShrink: 0,
              transition: "all 0.15s ease",
            }}
            aria-label="Toggle autonomous goal mode"
            title="Toggle Autonomous Goal Mode"
          >
            <Target size={12} />
            <span>Goal</span>
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
                  { cmd: "/code", label: "Build & Execute", icon: FolderGit2 },
                  { cmd: "/video", label: "Motion MP4", icon: Zap },
                  { cmd: "/image", label: "Image", icon: ImageIcon },
                  { cmd: "/document", label: "Document", icon: FileText },
                  { cmd: "/presentation", label: "Presentation", icon: Tv },
                  { cmd: "/research", label: "Research", icon: Globe },
                  { cmd: "/analyze", label: "Analysis", icon: Terminal },
                  { cmd: "/plan", label: "Plan", icon: Layout },
                ].map((item) => (
                  <button
                    key={item.cmd}
                    type="button"
                    onClick={() => {
                      onSelectArtifact?.(item.cmd);
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
          {onToggleLiveVision && (
            <button
              type="button"
              data-testid="composer-live-vision-btn"
              onClick={onToggleLiveVision}
              title={isLiveVisionActive ? "Stop Live Eyes (Screen Share)" : "Enable Live Eyes (Watch Screen)"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: isLiveVisionActive ? "rgba(16, 185, 129, 0.2)" : "var(--surface-subtle, #f6f3f7)",
                border: isLiveVisionActive ? "1px solid #10b981" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                color: isLiveVisionActive ? "#10b981" : "var(--text-secondary, #5e545d)",
                cursor: "pointer",
                transition: "all 0.15s ease",
                boxShadow: isLiveVisionActive ? "0 0 10px rgba(16, 185, 129, 0.4)" : "none",
              }}
            >
              <Eye size={15} />
            </button>
          )}

          {onVoiceToggle ? (
            <button
              type="button"
              data-testid="composer-voice-btn"
              onClick={onVoiceToggle}
              title={isVoiceActive ? "Mute / End Live Voice Call with Hina" : "Talk with Hina (Live Voice Call)"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: isVoiceActive ? "rgba(236, 72, 153, 0.25)" : "var(--surface-subtle, #f6f3f7)",
                border: isVoiceActive ? "1.5px solid #ec4899" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                color: isVoiceActive ? "#ec4899" : "var(--text-secondary, #5e545d)",
                cursor: "pointer",
                transition: "all 0.15s ease",
                boxShadow: isVoiceActive ? "0 0 12px rgba(236, 72, 153, 0.5)" : "none",
              }}
            >
              <Mic size={15} />
            </button>
          ) : voiceTyping.isSupported ? (
            <button
              type="button"
              data-testid="composer-voice-typing-btn"
              onClick={() => voiceTyping.toggleListening()}
              title={voiceTyping.isListening ? "Stop Voice Typing" : "Voice Typing (Continuous Speech Dictation)"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: voiceTyping.isListening ? "rgba(236, 72, 153, 0.2)" : "var(--surface-subtle, #f6f3f7)",
                border: voiceTyping.isListening ? "1px solid #ec4899" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                color: voiceTyping.isListening ? "#ec4899" : "var(--text-secondary, #5e545d)",
                cursor: "pointer",
                transition: "all 0.15s ease",
                boxShadow: voiceTyping.isListening ? "0 0 10px rgba(236, 72, 153, 0.4)" : "none",
              }}
            >
              <Mic size={15} />
            </button>
          ) : null}

          {onVoiceToggle && voiceTyping.isSupported && (
            <button
              type="button"
              data-testid="composer-voice-typing-btn"
              onClick={() => voiceTyping.toggleListening()}
              title={voiceTyping.isListening ? "Stop Dictation" : "Voice Dictation (Speech-to-Text into message)"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: voiceTyping.isListening ? "rgba(99, 102, 241, 0.2)" : "var(--surface-subtle, #f6f3f7)",
                border: voiceTyping.isListening ? "1px solid #6366f1" : "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
                color: voiceTyping.isListening ? "#6366f1" : "var(--text-secondary, #5e545d)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <FileText size={14} />
            </button>
          )}

          {isGenerating && !value.trim() && !attachedImage && extraImages.length === 0 && attachedDocuments.length === 0 ? (
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
              onPointerDown={() => {
                if (typeof window !== "undefined" && typeof (window as any).__hinaaUnlockAudio === "function") {
                  try { (window as any).__hinaaUnlockAudio(); } catch {}
                }
              }}
              onClick={() => {
                if (typeof window !== "undefined" && typeof (window as any).__hinaaUnlockAudio === "function") {
                  try { (window as any).__hinaaUnlockAudio(); } catch {}
                }
                if (value.trim() || attachedImage || extraImages.length > 0 || attachedDocuments.length > 0) {
                  playSendSound();
                  const attachedMediaPayload = [
                    ...extraImages.map((url, idx) => ({
                      name: `reference_image_${idx + 2}.png`,
                      kind: "image",
                      mimeType: "image/png",
                      dataUrl: url,
                    })),
                    ...attachedDocuments.map((d) => ({
                      name: d.name,
                      kind: d.kind.toLowerCase(),
                      mimeType: d.mimeType,
                      assetId: d.assetId,
                      textExcerpt: d.text,
                      contactSheetDataUrl: d.contactSheetDataUrl,
                    })),
                  ];
                  const inlineDocs = attachedDocuments.filter((d) => !d.assetId && d.kind !== "VIDEO" && d.text.trim());
                  const docContext = inlineDocs
                    .map((d) => `\n\n📄 [ATTACHED DOCUMENT: ${d.name} (${d.kind})]\n\`\`\`\n${d.text}\n\`\`\`\n`)
                    .join("\n");
                  const finalInput = value.trim()
                    ? (docContext ? `${value.trim()}\n${docContext}` : value.trim())
                    : attachedDocuments.length > 0
                      ? (docContext
                          ? `Please analyze this attached document:\n${docContext}`
                          : `Please inspect the attached files (${attachedDocuments.map((d) => d.name).join(", ")}).`)
                      : undefined;
                  setAttachedDocuments([]);
                  setExtraImages([]);
                  setUploadError(null);
                  if (finalInput !== undefined && finalInput !== value.trim()) onChange("");
                  if (isGenerating) onStop?.();
                  onSend({
                    text: finalInput,
                    mode: isGoalMode ? "goal" : actionMode,
                    intelligence: intelligenceLevel,
                    attachmentRole: selectedRole,
                    isGoalMode,
                    attachedMedia: attachedMediaPayload.length > 0 ? attachedMediaPayload : undefined,
                  });
                  return;
                }
                if (isGenerating) onStop?.();
                onSend({
                  mode: isGoalMode ? "goal" : actionMode,
                  intelligence: intelligenceLevel,
                  attachmentRole: selectedRole,
                  isGoalMode,
                });
              }}
              disabled={disabled || (!value.trim() && !attachedImage && extraImages.length === 0 && attachedDocuments.length === 0)}
              onMouseEnter={() => setSendHovered(true)}
              onMouseLeave={() => setSendHovered(false)}
              title="Send Message (Enter)"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                background:
                  !value.trim() && !attachedImage && extraImages.length === 0 && attachedDocuments.length === 0
                    ? (isDark ? "rgba(255, 255, 255, 0.08)" : "#f1f5f9")
                    : sendHovered
                      ? "linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)"
                      : (isDark ? "#f5f5f5" : "#1a232b"),
                color:
                  !value.trim() && !attachedImage && extraImages.length === 0 && attachedDocuments.length === 0
                    ? (isDark ? "rgba(255, 255, 255, 0.3)" : "var(--text-muted, #a198a0)")
                    : sendHovered
                      ? "#ffffff"
                      : (isDark ? "#1b1b1b" : "#ffffff"),
                border: "none",
                cursor: !value.trim() && !attachedImage && extraImages.length === 0 && attachedDocuments.length === 0 ? "not-allowed" : "pointer",
                boxShadow:
                  !value.trim() && !attachedImage && extraImages.length === 0 && attachedDocuments.length === 0
                    ? "none"
                    : sendHovered
                      ? "0 0 18px rgba(139, 92, 246, 0.6), 0 0 8px rgba(236, 72, 153, 0.45)"
                      : (isDark ? "0 2px 10px rgba(255, 255, 255, 0.25)" : "var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.1))"),
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
