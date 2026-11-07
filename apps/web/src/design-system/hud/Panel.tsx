import type { HTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

export interface PanelProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  actions?: ReactNode;
  /** Draw the thin HUD corner brackets. */
  brackets?: boolean;
  glass?: boolean;
  as?: "section" | "div" | "aside";
}

export function Panel({ title, actions, brackets = true, glass, as: Tag = "section", className, children, ...rest }: PanelProps) {
  return (
    <Tag className={clsx("ds-panel", glass && "ds-panel--glass", className)} {...rest}>
      {brackets && (
        <>
          <span className="ds-corner ds-corner--tl" aria-hidden="true" />
          <span className="ds-corner ds-corner--tr" aria-hidden="true" />
          <span className="ds-corner ds-corner--bl" aria-hidden="true" />
          <span className="ds-corner ds-corner--br" aria-hidden="true" />
        </>
      )}
      {(title || actions) && (
        <header className="ds-panel__head">
          <span>{title}</span>
          {actions}
        </header>
      )}
      <div className="ds-panel__body">{children}</div>
    </Tag>
  );
}
