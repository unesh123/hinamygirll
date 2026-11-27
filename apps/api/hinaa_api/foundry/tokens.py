"""Design tokens and WCAG 2.1 contrast math for HINAA Foundry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class FoundryPalette:
    name: str
    bg: str
    surface: str
    text: str
    muted: str
    accent: str
    accent_text: str
    border: str


FOUNDRY_PALETTES: Dict[str, FoundryPalette] = {
    "obsidian": FoundryPalette("obsidian", "#0b0f1c", "#131b2e", "#f8fafc", "#cbd5e1", "#22d3ee", "#042f2e", "#24324d"),
    "sakura": FoundryPalette("sakura", "#fff8fb", "#ffffff", "#1e1b2e", "#5b526e", "#be185d", "#ffffff", "#f3d6e4"),
    "terracotta": FoundryPalette("terracotta", "#faf6f0", "#ffffff", "#231914", "#5c4a3e", "#b45309", "#ffffff", "#e7d8c5"),
    "emerald": FoundryPalette("emerald", "#061a14", "#0c2920", "#ecfdf5", "#a7f3d0", "#10b981", "#022c22", "#144839"),
    "cobalt": FoundryPalette("cobalt", "#f5f8ff", "#ffffff", "#0f172a", "#475569", "#1d4ed8", "#ffffff", "#dbe4ff"),
    "ivory": FoundryPalette("ivory", "#fbfaf7", "#ffffff", "#18181b", "#52525b", "#0f766e", "#ffffff", "#e4e4e7"),
    "violet": FoundryPalette("violet", "#0f0a1e", "#191132", "#f5f3ff", "#c4b5fd", "#6d28d9", "#ffffff", "#31235c"),
    "coral": FoundryPalette("coral", "#fff9f7", "#ffffff", "#1f1210", "#5e433f", "#c2410c", "#ffffff", "#fed7aa"),
    "slate": FoundryPalette("slate", "#0f172a", "#1e293b", "#f1f5f9", "#cbd5e1", "#38bdf8", "#082f49", "#334155"),
    "mocha": FoundryPalette("mocha", "#1b1411", "#291e1a", "#faf5f0", "#d6c5ba", "#f59e0b", "#1b1411", "#44332d"),
    "amber": FoundryPalette("amber", "#fffbeb", "#ffffff", "#271705", "#614829", "#b45309", "#ffffff", "#fde68a"),
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    clean = hex_color.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(ch * 2 for ch in clean)
    if len(clean) != 6:
        raise ValueError(f"Invalid hex color: {hex_color!r}")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def _linear_channel(val: int) -> float:
    s = val / 255.0
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)
    return 0.2126 * _linear_channel(r) + 0.7152 * _linear_channel(g) + 0.0722 * _linear_channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    bright, dark = max(l1, l2), min(l1, l2)
    return round((bright + 0.05) / (dark + 0.05), 2)


def resolve_palette(name_or_hint: str | None) -> FoundryPalette:
    if name_or_hint:
        low = name_or_hint.strip().lower()
        if low in FOUNDRY_PALETTES:
            return FOUNDRY_PALETTES[low]
        for key, pal in FOUNDRY_PALETTES.items():
            if key in low:
                return pal
    return FOUNDRY_PALETTES["obsidian"]
