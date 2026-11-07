import type { HTMLAttributes } from "react";
import clsx from "clsx";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "neutral" | "success" | "warning" | "danger" | "accent";
  dot?: boolean;
}

export function Badge({ tone = "neutral", dot, className, children, ...rest }: BadgeProps) {
  return (
    <span className={clsx("ds-badge", tone !== "neutral" && `ds-badge--${tone}`, className)} {...rest}>
      {dot && <span className="ds-badge__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}
