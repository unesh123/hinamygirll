import type { ButtonHTMLAttributes } from "react";
import clsx from "clsx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: boolean;
}

export function Button({ variant = "secondary", icon, className, type = "button", ...rest }: ButtonProps) {
  return <button type={type} className={clsx("ds-btn", `ds-btn--${variant}`, icon && "ds-btn--icon", className)} {...rest} />;
}
