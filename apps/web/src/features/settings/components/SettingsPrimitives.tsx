/**
 * Settings primitive components.
 * Single file to keep the import surface small.
 */

import { type ReactNode, useId } from "react";
import styles from "./SettingsPrimitives.module.css";
import type { ProviderHealth } from "../../providers/types/provider";

// ── SettingsSection ──────────────────────────────────────────────────────────

interface SectionProps {
  label: string;
  children: ReactNode;
  divider?: boolean;
}

export function SettingsSection({ label, children, divider = false }: SectionProps) {
  return (
    <div className={styles.section}>
      {divider && <div className={styles.sectionDivider} aria-hidden="true" />}
      <div className={styles.sectionLabel} aria-hidden="true">
        {label}
      </div>
      {children}
    </div>
  );
}

// ── SettingsRow ──────────────────────────────────────────────────────────────

interface RowProps {
  label: string;
  description?: string;
  children: ReactNode;
  htmlFor?: string;
}

export function SettingsRow({ label, description, children, htmlFor }: RowProps) {
  return (
    <div className={styles.row}>
      <label className={styles.rowLabel} htmlFor={htmlFor}>
        <span className={styles.rowTitle}>{label}</span>
        {description && (
          <span className={styles.rowDescription}>{description}</span>
        )}
      </label>
      <div className={styles.rowControl}>{children}</div>
    </div>
  );
}

// ── SettingsSelect ────────────────────────────────────────────────────────────

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps {
  id?: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  "aria-label"?: string;
}

export function SettingsSelect({
  id,
  value,
  options,
  onChange,
  disabled = false,
  "aria-label": ariaLabel,
}: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <select
      id={selectId}
      className={styles.select}
      value={value}
      onChange={(e) => onChange(e.currentTarget.value)}
      disabled={disabled}
      aria-label={ariaLabel}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value} disabled={opt.disabled}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

// ── SettingsToggle ────────────────────────────────────────────────────────────

interface ToggleProps {
  id?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  "aria-label"?: string;
}

export function SettingsToggle({
  id,
  checked,
  onChange,
  disabled = false,
  "aria-label": ariaLabel,
}: ToggleProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className={styles.toggleWrapper}>
      <input
        id={inputId}
        type="checkbox"
        role="switch"
        className={styles.toggleInput}
        checked={checked}
        onChange={(e) => onChange(e.currentTarget.checked)}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-checked={checked}
      />
      <div className={styles.toggleTrack} aria-hidden="true" />
      <div className={styles.toggleThumb} aria-hidden="true" />
    </div>
  );
}

// ── SettingsStatus ────────────────────────────────────────────────────────────

const HEALTH_LABELS: Record<ProviderHealth, string> = {
  healthy:     "Available",
  degraded:    "Degraded",
  unavailable: "Unavailable",
  disabled:    "Disabled",
  checking:    "Checking…",
  unknown:     "Unknown",
};

interface StatusProps {
  health: ProviderHealth;
  label?: string;
}

export function SettingsStatus({ health, label }: StatusProps) {
  return (
    <span
      className={styles.statusPill}
      data-health={health}
      role="status"
      aria-live="polite"
    >
      <span className={styles.statusDot} aria-hidden="true" />
      {label ?? HEALTH_LABELS[health]}
    </span>
  );
}
