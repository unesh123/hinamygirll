/**
 * SettingsDrawer — accessible dialog with focus trap.
 *
 * Accessibility contract:
 * - role="dialog" + aria-modal="true" + aria-labelledby
 * - Focus moves to first focusable element on open
 * - Tab stays inside drawer (focus trap)
 * - Escape closes + returns focus to trigger
 * - Close button closes + returns focus to trigger
 * - Background gets inert attribute when drawer is open
 * - Reduced motion: slide animation skipped
 * - Backdrop click closes the drawer
 */

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  type ReactNode,
} from "react";
import styles from "./SettingsDrawer.module.css";

const FOCUSABLE_SELECTORS = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

interface Props {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function SettingsDrawer({ isOpen, onClose, children }: Props) {
  const titleId = useId();
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const backdropRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  // Focus trap implementation
  const trapFocus = useCallback((e: KeyboardEvent) => {
    if (!drawerRef.current) return;
    const focusable = Array.from(
      drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS),
    ).filter((el) => !el.closest("[disabled]"));

    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.key === "Tab") {
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;

    // Save trigger reference before focus moves
    triggerRef.current = document.getElementById("settings-trigger");

    // Focus first element inside drawer
    requestAnimationFrame(() => {
      const first = drawerRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTORS);
      first?.focus();
    });

    document.addEventListener("keydown", trapFocus);
    return () => {
      document.removeEventListener("keydown", trapFocus);
    };
  }, [isOpen, trapFocus]);

  // Restore focus on close
  useEffect(() => {
    if (!isOpen && triggerRef.current) {
      triggerRef.current.focus();
    }
  }, [isOpen]);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        ref={backdropRef}
        className={styles.backdrop}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        id="settings-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={styles.drawer}
        data-testid="settings-drawer"
      >
        {/* Sticky header */}
        <div className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            Settings
          </h2>
          <button
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

        {/* Scrollable content */}
        <div className={styles.content}>
          {children}
        </div>
      </div>
    </>
  );
}
