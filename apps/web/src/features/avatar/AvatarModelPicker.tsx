import React, { useEffect, useState, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Sparkles, Upload, Settings } from "lucide-react";
import { AVATAR_REGISTRY, type AvatarDefinition } from "./avatarRegistry";

interface AvatarModelPickerProps {
  isOpen: boolean;
  onClose: () => void;
  triggerRef: React.RefObject<HTMLElement | null>;
  currentModel?: string;
  onSelectModel: (modelUrl: string) => void;
  onOpenAvatarLab?: () => void;
}

export const AvatarModelPicker: React.FC<AvatarModelPickerProps> = ({
  isOpen,
  onClose,
  triggerRef,
  currentModel,
  onSelectModel,
  onOpenAvatarLab,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number; width: number } | null>(null);
  const [importStatus, setImportStatus] = useState<string | null>(null);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const menuWidth = 280;
    let left = rect.right - menuWidth;
    if (left < 16) left = 16;
    if (left + menuWidth > window.innerWidth - 16) {
      left = window.innerWidth - menuWidth - 16;
    }
    const top = rect.bottom + 8;
    setCoords({ top, left, width: menuWidth });
  }, [triggerRef]);

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      const handleScrollOrResize = () => updatePosition();
      window.addEventListener("scroll", handleScrollOrResize, true);
      window.addEventListener("resize", handleScrollOrResize);
      return () => {
        window.removeEventListener("scroll", handleScrollOrResize, true);
        window.removeEventListener("resize", handleScrollOrResize);
      };
    }
  }, [isOpen, updatePosition]);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (menuRef.current && !menuRef.current.contains(target) && triggerRef.current && !triggerRef.current.contains(target)) {
        onClose();
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside, true);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside, true);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose, triggerRef]);

  const handleCustomImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.currentTarget.value = "";
    setImportStatus(`Importing ${file.name}…`);
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const response = await fetch("/api/v1/avatar-assets/import", {
        method: "POST",
        body: form,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok || !body?.asset?.browserUrl) {
        throw new Error(body?.detail || "HINAA could not save that VRM yet.");
      }
      onSelectModel(body.asset.browserUrl);
      onClose();
    } catch (error) {
      // Last-resort local preview: useful while the API is offline, but App
      // intentionally does not persist blob/data URLs because they die on reload.
      const objectUrl = URL.createObjectURL(file);
      onSelectModel(objectUrl);
      setImportStatus(
        error instanceof Error
          ? `${error.message} Previewing this VRM for this tab only. Use Avatar Lab once the API is online to keep it after reload.`
          : "Previewing this VRM for this tab only. Use Avatar Lab once the API is online to keep it after reload.",
      );
    }
  };

  if (!isOpen || typeof document === "undefined") return null;

  // Deduplicate avatars by fileUrl
  const seenUrls = new Set<string>();
  const uniqueAvatars: AvatarDefinition[] = [];
  for (const av of AVATAR_REGISTRY) {
    if (!seenUrls.has(av.fileUrl)) {
      seenUrls.add(av.fileUrl);
      uniqueAvatars.push(av);
    }
  }

  return createPortal(
    <AnimatePresence>
      <motion.div
        ref={menuRef}
        role="dialog"
        aria-label="Select Companion Avatar"
        initial={{ opacity: 0, y: -6, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -6, scale: 0.97 }}
        transition={{ duration: 0.14, ease: [0.22, 1, 0.36, 1] }}
        style={{
          position: "fixed",
          top: coords ? coords.top : 100,
          left: coords ? coords.left : 100,
          width: coords ? coords.width : 280,
          maxHeight: "min(440px, calc(100vh - 120px))",
          overflowY: "auto",
          background: "var(--bg-surface-raised, #18181b)",
          border: "1px solid var(--border-default, #27272a)",
          borderRadius: "var(--radius-xl, 14px)",
          boxShadow: "0 14px 35px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.06)",
          padding: 6,
          zIndex: 99999,
          display: "flex",
          flexDirection: "column",
          gap: 3,
          backdropFilter: "blur(20px)",
        }}
      >
        <div
          style={{
            padding: "6px 10px 4px",
            fontSize: "0.68rem",
            fontWeight: 700,
            color: "var(--text-tertiary, #a1a1aa)",
            textTransform: "uppercase",
            letterSpacing: 0.6,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Sparkles size={11} color="var(--accent, #f472b6)" />
          <span>Select Companion Model</span>
        </div>

        {uniqueAvatars.map((avatar) => {
          const isSelected =
            avatar.fileUrl === currentModel ||
            (!currentModel && (avatar.id === "hinaa-original" || avatar.id === "hinaa-default"));

          return (
            <button
              key={avatar.id}
              type="button"
              onClick={() => {
                onSelectModel(avatar.fileUrl);
                onClose();
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                borderRadius: "var(--radius-md, 8px)",
                border: "none",
                background: isSelected ? "var(--accent-pale, rgba(244,114,182,0.12))" : "transparent",
                color: isSelected ? "var(--accent, #f472b6)" : "var(--text-primary, #ffffff)",
                cursor: "pointer",
                textAlign: "left",
                transition: "background 0.12s ease",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) e.currentTarget.style.background = "var(--bg-surface-hover, rgba(255,255,255,0.06))";
              }}
              onMouseLeave={(e) => {
                if (!isSelected) e.currentTarget.style.background = "transparent";
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                <span style={{ fontSize: "var(--text-xs, 0.78rem)", fontWeight: isSelected ? 700 : 500 }}>
                  {avatar.name}
                </span>
                <span
                  style={{
                    fontSize: "0.66rem",
                    color: "var(--text-tertiary, #9ca3af)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: 210,
                  }}
                >
                  {avatar.description}
                </span>
              </div>
              {isSelected && <Check size={14} color="var(--accent, #f472b6)" style={{ flexShrink: 0 }} />}
            </button>
          );
        })}

        <div style={{ height: 1, background: "var(--border-subtle, #27272a)", margin: "4px 0" }} />

        {importStatus && (
          <div
            role="status"
            style={{
              padding: "6px 10px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent-pale, rgba(244,114,182,0.12))",
              color: "var(--text-secondary, #e4e4e7)",
              fontSize: "0.68rem",
              lineHeight: 1.35,
            }}
          >
            {importStatus}
          </div>
        )}

        {/* Import custom VRM button */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".vrm"
          onChange={handleCustomImport}
          style={{ display: "none" }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 10px",
            borderRadius: "var(--radius-md, 8px)",
            border: "none",
            background: "transparent",
            color: "var(--text-secondary, #e4e4e7)",
            cursor: "pointer",
            fontSize: "var(--text-xs, 0.78rem)",
            fontWeight: 500,
            textAlign: "left",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-surface-hover, rgba(255,255,255,0.06))";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          <Upload size={13} color="var(--text-tertiary, #a1a1aa)" />
          <span>+ Import custom .vrm</span>
        </button>

        {onOpenAvatarLab && (
          <button
            type="button"
            onClick={() => {
              onOpenAvatarLab();
              onClose();
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 10px",
              borderRadius: "var(--radius-md, 8px)",
              border: "none",
              background: "transparent",
              color: "var(--text-secondary, #e4e4e7)",
              cursor: "pointer",
              fontSize: "var(--text-xs, 0.78rem)",
              fontWeight: 500,
              textAlign: "left",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-surface-hover, rgba(255,255,255,0.06))";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            <Settings size={13} color="var(--text-tertiary, #a1a1aa)" />
            <span>Avatar Studio & Settings</span>
          </button>
        )}
      </motion.div>
    </AnimatePresence>,
    document.body
  );
};
