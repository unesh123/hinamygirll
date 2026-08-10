# HINAA Document 58: UI Visual System & Design Tokens Specification

## Overview
This document specifies the refreshed visual design system for the HINAA companion interface. The visual system adheres strictly to modern glassmorphism, responsive viewports, high-contrast typography, and performance-conscious animation constraints.

## Theme & Palette Tokens
- **Background Root (`--color-bg-root`)**: `#0a0a0f` (Deep Space Dark)
- **Panel Surface (`--color-surface-glass`)**: `rgba(18, 15, 31, 0.72)` with `backdrop-filter: blur(16px)`
- **Border Prism (`--color-border-glass`)**: `rgba(255, 255, 255, 0.12)`
- **Accent Primary (`--color-accent-hinaa`)**: `#8a5cf6` (Electric Iris)
- **Accent Secondary (`--color-accent-hiro`)**: `#3b82f6` (Cyan-Blue Spark)
- **Text Primary (`--color-text-primary`)**: `#f3f4f6` (High contrast WCAG AAA compliant)
- **Text Muted (`--color-text-muted`)**: `#9ca3af`

## Design Principles & Guardrails
1. **Calm Glassmorphism**: Glass blur capped at 16px to prevent mobile GPU shader throttling.
2. **Restrained Ambient Glow**: Radial gradient background is static; no continuous multi-point light animations.
3. **Typography**: Uses system font stack (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`, `sans-serif`) with explicit line-height and letter-spacing for high readability.
4. **Motion Safety**: Respects `prefers-reduced-motion: reduce`. Continuous breathing animations are disabled when reduced motion is requested.
5. **No Layout Shift**: Autoresizes composer height without pushing the transcript viewport off-screen.
