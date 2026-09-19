export interface AvatarDefinition {
  id: string;
  name: string;
  description: string;
  fileUrl: string;
  companionId: "hinaa" | "hiro";
  defaultForCompanion?: boolean;
}

export const DEFAULT_COMPANION_ID = "hinaa-original";
// URL-safe filename. The original bundled asset is named
// "5798998195377315936 (1).vrm"; its space and parentheses made the encoded
// request fall through Vercel's SPA rewrite and return index.html instead of
// the model — which is why the default 3D avatar failed to load in production.
export const DEFAULT_AVATAR_FILE = "/models/hinaa-original.vrm";

export const AVATAR_REGISTRY: AvatarDefinition[] = [
  {
    id: "hinaa-original",
    name: "Hinaa (Original)",
    description: "Default Hinaa companion with pink ribbons and cat ears",
    fileUrl: "/models/hinaa-original.vrm",
    companionId: "hinaa",
    defaultForCompanion: true,
  },
  {
    id: "hinaa-default",
    name: "Hinaa (Original)",
    description: "Default Hinaa companion with pink ribbons and cat ears",
    fileUrl: "/models/hinaa-original.vrm",
    companionId: "hinaa",
  },
  {
    id: "hinaa-classic",
    name: "Hinaa Classic",
    description: "Classic Hinaa VRoid companion avatar",
    fileUrl: "/models/hinaa.vrm",
    companionId: "hinaa",
  },
  {
    id: "hinaa-schoolgirl",
    name: "Sakura Student (Sample E)",
    description: "Anime school uniform model with lightweight geometry",
    fileUrl: "/models/AvatarSample_E.vrm",
    companionId: "hinaa",
  },
  {
    id: "hinaa-casual",
    name: "Hinaa Casual (5447)",
    description: "Modern casual streetwear avatar",
    fileUrl: "/models/model_5447.vrm",
    companionId: "hinaa",
  },
  {
    id: "hinaa-kimono",
    name: "Hinaa Kimono (6164)",
    description: "Traditional festive Japanese kimono avatar",
    fileUrl: "/models/model_6164.vrm",
    companionId: "hinaa",
  },
  {
    id: "hiro-default",
    name: "Hiro (Companion)",
    description: "Companion avatar for Hiro voice profile",
    fileUrl: "/models/AvatarSample_E.vrm",
    companionId: "hiro",
    defaultForCompanion: true,
  },
];

export function getAvatarById(id: string): AvatarDefinition {
  if (id === "hinaa-default") return AVATAR_REGISTRY[0];
  return (
    AVATAR_REGISTRY.find((a) => a.id === id) ??
    AVATAR_REGISTRY[0]
  );
}

export function getDefaultAvatarForCompanion(
  companionId: "hinaa" | "hiro",
): AvatarDefinition {
  return (
    AVATAR_REGISTRY.find(
      (a) => a.companionId === companionId && a.defaultForCompanion,
    ) ?? AVATAR_REGISTRY[0]
  );
}

export function resolveValidAvatarModel(savedModelUrl?: string | null): string {
  if (!savedModelUrl) return DEFAULT_AVATAR_FILE;
  const match = AVATAR_REGISTRY.find((a) => a.fileUrl === savedModelUrl);
  if (match) return match.fileUrl;
  if (/^\/api\/v1\/avatar-assets\/avatar-[0-9a-f-]+\/file$/i.test(savedModelUrl)) {
    return savedModelUrl;
  }
  return DEFAULT_AVATAR_FILE;
}

export const AVATAR_SELECTION_KEY = "hinaa.avatar-selection.v1";
export const LEGACY_AVATAR_SELECTION_KEY = "hinaa.avatar-model";
const managedAvatar = /^\/api\/v1\/avatar-assets\/avatar-[0-9a-f-]+\/file$/i;

export function isSelectableAvatarUrl(value: string | null): value is string {
  return Boolean(value && (AVATAR_REGISTRY.some((avatar) => avatar.fileUrl === value) || managedAvatar.test(value) || value.startsWith("blob:")));
}

export function persistAvatarSelection(storage: Pick<Storage, "setItem">, url: string): void {
  if (!isSelectableAvatarUrl(url) || url.startsWith("blob:")) return;
  const avatar = AVATAR_REGISTRY.find((entry) => entry.fileUrl === url);
  storage.setItem(AVATAR_SELECTION_KEY, JSON.stringify(avatar ? { id: avatar.id } : { customAssetUrl: url }));
  storage.setItem(LEGACY_AVATAR_SELECTION_KEY, url);
}

export function readAvatarSelection(storage: Pick<Storage, "getItem" | "setItem">): string {
  try {
    const saved = JSON.parse(storage.getItem(AVATAR_SELECTION_KEY) ?? "null");
    const avatar = AVATAR_REGISTRY.find((entry) => entry.id === saved?.id);
    if (avatar) return avatar.fileUrl;
    if (typeof saved?.customAssetUrl === "string" && managedAvatar.test(saved.customAssetUrl)) return saved.customAssetUrl;
  } catch { /* An old or invalid record can still have a valid legacy URL. */ }
  const url = resolveValidAvatarModel(storage.getItem(LEGACY_AVATAR_SELECTION_KEY));
  try { persistAvatarSelection(storage, url); } catch { /* Storage may be read-only. */ }
  return url;
}
