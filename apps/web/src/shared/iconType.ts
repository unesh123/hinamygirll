import type { ComponentType, CSSProperties } from "react";

/**
 * Concrete props signature for lucide-react icon components.
 *
 * `React.ElementType` maps stored icons to `never`-typed props under
 * TypeScript 7's stricter JSX resolution, so dynamic icon maps use this
 * explicit component type instead.
 */
export type IconComponent = ComponentType<{
  size?: number | string;
  color?: string;
  strokeWidth?: number | string;
  style?: CSSProperties;
  className?: string;
}>;
