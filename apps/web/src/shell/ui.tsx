import type { ReactNode } from "react";
import { Button } from "../design-system/hud";
import type { ApiStatus } from "./useApi";

export interface ResourceStateProps {
  status: ApiStatus;
  error?: string | null;
  empty?: boolean;
  /** Plain-language name used in messages, e.g. "connectors". */
  noun: string;
  onRetry?: () => void;
  children: ReactNode;
}

/** Shared loading / not-available / error / empty handling for API-backed panels. */
export function ResourceState({ status, error, empty, noun, onRetry, children }: ResourceStateProps) {
  if (status === "loading") return <p className="shell-state" role="status">Loading {noun}…</p>;
  if (status === "missing") {
    return <p className="shell-state" data-kind="missing">The {noun} endpoint isn’t available on this backend yet.</p>;
  }
  if (status === "error") {
    return (
      <div className="shell-state" data-kind="error" role="alert">
        <span>Couldn’t load {noun}{error ? ` — ${error}` : ""}.</span>
        {onRetry && <Button variant="secondary" onClick={onRetry}>Retry</Button>}
      </div>
    );
  }
  if (empty) return <p className="shell-state" data-kind="empty">No {noun} yet.</p>;
  return <>{children}</>;
}

export function PageFrame({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <main className="shell-page" aria-labelledby="shell-page-title">
      <div className="shell-page__inner">
        <h1 id="shell-page-title" className="shell-page__title">{title}</h1>
        {subtitle && <p className="shell-page__sub">{subtitle}</p>}
        {children}
      </div>
    </main>
  );
}
