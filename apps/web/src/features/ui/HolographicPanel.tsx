import React, { useEffect, useRef } from "react";
import styles from "./HolographicPanel.module.css";

export interface HolographicPanelProps {
  isOpen: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  docked?: boolean;
  onToggleDock?: () => void;
}

export function HolographicPanel({
  isOpen,
  title,
  onClose,
  children,
  docked = false,
  onToggleDock,
}: HolographicPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose} role="presentation">
      <div
        className={`${styles.panel} ${docked ? styles.docked : ""}`}
        onClick={(e) => e.stopPropagation()}
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          <div className={styles.actions}>
            {onToggleDock && (
              <button
                type="button"
                className={styles.dockBtn}
                onClick={onToggleDock}
                aria-label={docked ? "Expand panel" : "Dock panel"}
              >
                {docked ? "⤢" : "⤡"}
              </button>
            )}
            <button
              type="button"
              className={styles.closeBtn}
              onClick={onClose}
              aria-label="Close panel"
            >
              ✕
            </button>
          </div>
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  );
}
