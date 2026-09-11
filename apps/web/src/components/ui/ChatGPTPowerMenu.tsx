import React, { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Paperclip,
  BookOpen,
  Image as ImageIcon,
  Globe,
  Brain,
  Presentation,
  Cpu,
  GitBranch,
  Sparkles,
} from "lucide-react";

export interface PowerMenuItem {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  iconColor: string;
  action: () => void;
  badge?: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onUploadFile: () => void;
  onSelectAction: (command: string) => void;
  onOpenLibrary: () => void;
}

export function ChatGPTPowerMenu({
  isOpen,
  onClose,
  onUploadFile,
  onSelectAction,
  onOpenLibrary,
}: Props) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const items: PowerMenuItem[] = [
    {
      id: "upload",
      title: "Add photos & files",
      subtitle: "Upload from computer (or paste Ctrl+V)",
      icon: <Paperclip size={18} />,
      iconColor: "#a1a1aa",
      action: () => {
        onClose();
        onUploadFile();
      },
    },
    {
      id: "library",
      title: "Add from library",
      subtitle: "Browse and search your files",
      icon: <BookOpen size={18} />,
      iconColor: "#38bdf8",
      action: () => {
        onClose();
        onOpenLibrary();
      },
    },
    {
      id: "create_image",
      title: "Create image",
      subtitle: "Visualize anything with HINAA Diffusion",
      icon: <ImageIcon size={18} />,
      iconColor: "#ec4899",
      action: () => {
        onClose();
        onSelectAction("/generate ");
      },
    },
    {
      id: "web_search",
      title: "Web search",
      subtitle: "Find real-time news and info",
      icon: <Globe size={18} />,
      iconColor: "#06b6d4",
      action: () => {
        onClose();
        onSelectAction("/search ");
      },
    },
    {
      id: "deep_research",
      title: "Deep research",
      subtitle: "Get a detailed cited report",
      icon: <Brain size={18} />,
      iconColor: "#8b5cf6",
      action: () => {
        onClose();
        onSelectAction("/research ");
      },
    },
    {
      id: "presentation",
      title: "Presentation & Slides",
      subtitle: "Generate pitch decks with Gamma / Beautiful.ai",
      icon: <Presentation size={18} />,
      iconColor: "#f97316",
      action: () => {
        onClose();
        onSelectAction("/gamma ");
      },
    },
    {
      id: "agent_brain",
      title: "AI Brain Provider",
      subtitle: "Switch between CX Gateway & Gemini Flash",
      icon: <Cpu size={18} />,
      iconColor: "#10b981",
      action: () => {
        onClose();
        onSelectAction("/model ");
      },
      badge: "Active",
    },
    {
      id: "github",
      title: "GitHub Triage",
      subtitle: "Inspect issues, PRs, and commits",
      icon: <GitBranch size={18} />,
      iconColor: "#ffffff",
      action: () => {
        onClose();
        onSelectAction("/git status");
      },
      badge: "Connect",
    },
  ];

  return (
    <AnimatePresence>
      <motion.div
        ref={menuRef}
        role="dialog"
        aria-label="Add capabilities"
        initial={{ opacity: 0, y: 12, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.96 }}
        transition={{ duration: 0.16, ease: [0.22, 0.61, 0.36, 1] }}
        style={{
          position: "absolute",
          bottom: "calc(100% + 10px)",
          left: 0,
          zIndex: 300,
          width: "min(380px, calc(100vw - 28px))",
          background: "var(--bg-surface)",
          backdropFilter: "blur(24px)",
          WebkitBackdropFilter: "blur(24px)",
          borderRadius: 20,
          border: "1px solid var(--border-default)",
          boxShadow: "var(--shadow-xl, 0 16px 40px rgba(0,0,0,0.35))",
          padding: "8px",
          display: "flex",
          flexDirection: "column",
          gap: 2,
          overflow: "hidden",
        }}
      >
        <div style={{ maxHeight: 420, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={item.action}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 12px",
                borderRadius: 12,
                border: "none",
                background: "transparent",
                color: "var(--text-primary)",
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "inherit",
                transition: "background 0.12s ease",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-surface-raised)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: `${item.iconColor}18`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: item.iconColor,
                  flexShrink: 0,
                }}
              >
                {item.icon}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "0.85rem", fontWeight: 650, color: "var(--text-primary)" }}>
                  {item.title}
                </div>
                <div
                  style={{
                    fontSize: "0.72rem",
                    color: "var(--text-secondary)",
                    marginTop: 1,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {item.subtitle}
                </div>
              </div>

              {item.badge && (
                <span
                  style={{
                    fontSize: "0.68rem",
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: 10,
                    background: "var(--bg-secondary)",
                    color: "var(--text-tertiary)",
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        <div
          style={{
            borderTop: "1px solid var(--border-subtle)",
            marginTop: 4,
            padding: "8px 12px 4px",
            fontSize: "0.7rem",
            color: "var(--text-tertiary)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Sparkles size={12} color="var(--accent)" />
          <span>Type / to search tools, skills & plugins</span>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
