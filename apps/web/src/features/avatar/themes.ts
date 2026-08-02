export type AvatarThemeId =
  "soft" | "futuristic" | "anime-inspired-original" | "minimal" | "night";

export interface AvatarTheme {
  id: AvatarThemeId;
  label: string;
  description: string;
  className: string;
  lowGpu: boolean;
}

export const AVATAR_THEMES: AvatarTheme[] = [
  {
    id: "soft",
    label: "Soft",
    description: "Gentle gradients and rounded motion cues",
    className: "theme-soft",
    lowGpu: false,
  },
  {
    id: "futuristic",
    label: "Futuristic",
    description: "Clean luminous accents without heavy glow spam",
    className: "theme-futuristic",
    lowGpu: false,
  },
  {
    id: "anime-inspired-original",
    label: "Expressive",
    description:
      "Original expressive stylization — not a copyrighted character",
    className: "theme-expressive",
    lowGpu: false,
  },
  {
    id: "minimal",
    label: "Minimal",
    description: "Low-GPU simple avatar for weaker devices",
    className: "theme-minimal",
    lowGpu: true,
  },
  {
    id: "night",
    label: "Night",
    description: "Darker interface with accessible contrast",
    className: "theme-night",
    lowGpu: false,
  },
];

const STORAGE_KEY = "hinaa.avatarTheme";

export function loadAvatarTheme(): AvatarThemeId {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (AVATAR_THEMES.some((theme) => theme.id === value))
      return value as AvatarThemeId;
  } catch {
    /* ignore */
  }
  return "soft";
}

export function saveAvatarTheme(id: AvatarThemeId): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}
