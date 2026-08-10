/**
 * SettingsDialog — native <dialog> implementation.
 *
 * Uses showModal() for:
 * - Native focus trap (browser-provided)
 * - Escape key handling (browser-provided)
 * - Proper modal interaction isolation (inert + top-layer)
 * - Native ::backdrop support
 * - Semantic dialog role
 *
 * We only add:
 * - aria-labelledby
 * - Focus restoration to trigger on close
 * - Initial focus on close button (useful starting point)
 * - Scroll lock on <body>
 * - Mobile bottom-sheet layout
 */

import {
  type ReactNode,
  useEffect,
  useId,
  useRef,
} from "react";
import styles from "./SettingsDialog.module.css";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function SettingsDialog({ isOpen, onClose, children }: Props) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const titleId = useId();
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);

  // Open/close the native dialog
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      if (!dialog.open) {
        dialog.showModal();
        // Initial focus: close button is a useful, non-destructive starting point
        requestAnimationFrame(() => closeBtnRef.current?.focus());
      }
      document.body.style.overflow = "hidden";
    } else {
      if (dialog.open) {
        dialog.close();
      }
      document.body.style.overflow = "";
      // Restore focus to the trigger button
      const trigger = document.getElementById("settings-trigger");
      trigger?.focus();
    }

    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  // Handle the native Escape close event (dispatched by the browser)
  // and the close event (dispatched by dialog.close())
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleCancel = (e: Event) => {
      e.preventDefault(); // We handle close ourselves to restore focus
      onClose();
    };
    dialog.addEventListener("cancel", handleCancel);
    return () => dialog.removeEventListener("cancel", handleCancel);
  }, [onClose]);

  // Backdrop click (clicks on the <dialog> itself, outside the panel)
  const handleDialogClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) {
      onClose();
    }
  };

  return (
    <dialog
      ref={dialogRef}
      id="settings-dialog"
      className={styles.dialog}
      aria-labelledby={titleId}
      aria-modal="true"
      data-testid="settings-dialog"
      onClick={handleDialogClick}
    >
      {/* Inner panel — click here does NOT close (stops propagation) */}
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* Sticky header */}
        <div className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            Settings
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close settings"
          >
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" width="16" height="16">
              <path
                d="M5 5l10 10M15 5L5 15"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        {/* Scrollable content area */}
        <div className={styles.content}>
          {children}
        </div>
      </div>
    </dialog>
  );
}
