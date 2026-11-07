import type { HTMLAttributes } from "react";
import clsx from "clsx";

export function Kbd({ className, ...rest }: HTMLAttributes<HTMLElement>) {
  return <kbd className={clsx("ds-kbd", className)} {...rest} />;
}
