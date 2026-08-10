// HinaDrawer — Smart animated drawer for Hinaa's rich responses
// Adapted from lightswind.com — triggers via voice or programmatically

import * as React from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Image as ImageIcon, FileText, Globe, Music, Sparkles } from "lucide-react";

type DrawerSide = "top" | "bottom" | "left" | "right";
type DrawerMode = "info" | "image" | "web" | "music" | "slides" | "code";

interface HinaDrawerProps {
  open: boolean;
  onClose: () => void;
  side?: DrawerSide;
  mode?: DrawerMode;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}

const slideVariants: Record<DrawerSide, { initial: any; animate: any; exit: any }> = {
  bottom: { initial: { y: "100%", opacity: 0.5 }, animate: { y: 0, opacity: 1 }, exit: { y: "100%", opacity: 0 } },
  top:    { initial: { y: "-100%", opacity: 0.5 }, animate: { y: 0, opacity: 1 }, exit: { y: "-100%", opacity: 0 } },
  left:   { initial: { x: "-100%", opacity: 0.5 }, animate: { x: 0, opacity: 1 }, exit: { x: "-100%", opacity: 0 } },
  right:  { initial: { x: "100%", opacity: 0.5 }, animate: { x: 0, opacity: 1 }, exit: { x: "100%", opacity: 0 } },
};

const modeIcons: Record<DrawerMode, React.ReactNode> = {
  info:   <FileText size={16} />,
  image:  <ImageIcon size={16} />,
  web:    <Globe size={16} />,
  music:  <Music size={16} />,
  slides: <Sparkles size={16} />,
  code:   <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{"{}"}</span>,
};

const modeColors: Record<DrawerMode, string> = {
  info:   "#8b5cf6",
  image:  "#f59e0b",
  web:    "#06b6d4",
  music:  "#ef4444",
  slides: "#10b981",
  code:   "#6366f1",
};

export function HinaDrawer({
  open,
  onClose,
  side = "bottom",
  mode = "info",
  title,
  children,
  className = "",
}: HinaDrawerProps) {
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const v = slideVariants[side];
  const color = modeColors[mode];

  const sideClass = {
    bottom: "hina-drawer-bottom",
    top:    "hina-drawer-top",
    left:   "hina-drawer-left",
    right:  "hina-drawer-right",
  }[side];

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className={`hina-drawer-overlay-wrap ${sideClass}`}>
          {/* Backdrop */}
          <motion.div
            className="hina-drawer-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
          />

          {/* Drawer panel */}
          <motion.div
            className={`hina-drawer-panel ${sideClass} ${className}`}
            initial={v.initial}
            animate={v.animate}
            exit={v.exit}
            transition={{ type: "spring", damping: 26, stiffness: 320 }}
          >
            {/* Handle bar (bottom drawer) */}
            {side === "bottom" && <div className="hina-drawer-handle" />}

            {/* Header */}
            <div className="hina-drawer-header" style={{ "--drawer-accent": color } as React.CSSProperties}>
              <span className="hina-drawer-mode-icon" style={{ color }}>{modeIcons[mode]}</span>
              <span className="hina-drawer-title">{title || `Hinaa — ${mode}`}</span>
              <motion.button
                className="hina-drawer-close"
                onClick={onClose}
                whileHover={{ scale: 1.1, rotate: 90 }}
                whileTap={{ scale: 0.9 }}
              >
                <X size={18} />
              </motion.button>
            </div>

            {/* Content */}
            <div className="hina-drawer-body">
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}

// ── Exported sub-components ────────────────────────────────────────────────
export function DrawerTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="hina-drawer-section-title">{children}</h3>;
}

export function DrawerDescription({ children }: { children: React.ReactNode }) {
  return <p className="hina-drawer-section-desc">{children}</p>;
}
