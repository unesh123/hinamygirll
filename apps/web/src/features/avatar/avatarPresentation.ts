export type AvatarPoseMode = "relaxed" | "original";

export type AvatarPresentation = {
  /** Root Y rotation in radians; this changes only the browser scene. */
  rotationY: number;
  /** Browser-scene ground offset; this does not alter the VRM file. */
  offsetY: number;
  /** Bounded browser-scene scale. */
  scale: number;
  /** Relaxed uses normalized humanoid offsets; original restores authored rest. */
  poseMode: AvatarPoseMode;
};

export const AVATAR_PRESENTATION_STORAGE_KEY = "hinaa.avatar-presentation.v1";

const KNOWN_PRESENTATIONS: Record<string, AvatarPresentation> = {
  "/models/model_6164.vrm": { rotationY: Math.PI, offsetY: -0.24, scale: 0.90, poseMode: "relaxed" },
  "/models/model_5447.vrm": { rotationY: 0, offsetY: 0, scale: 1, poseMode: "relaxed" },
};

export function defaultAvatarPresentation(modelUrl: string): AvatarPresentation {
  const known = KNOWN_PRESENTATIONS[modelUrl];
  if (known) return { ...known };
  // Imported models commonly look backward after their VRM-version conversion.
  // The browser can reverse this in one click; we never rewrite their binary.
  return { rotationY: Math.PI, offsetY: 0, scale: 1, poseMode: "relaxed" };
}

export function normalizeAvatarPresentation(value: Partial<AvatarPresentation> | undefined, modelUrl: string): AvatarPresentation {
  const fallback = defaultAvatarPresentation(modelUrl);
  const rotationY = typeof value?.rotationY === "number" && Number.isFinite(value.rotationY)
    ? value.rotationY : fallback.rotationY;
  const offsetY = typeof value?.offsetY === "number" && Number.isFinite(value.offsetY)
    ? Math.max(-1.5, Math.min(1.5, value.offsetY)) : fallback.offsetY;
  const scale = typeof value?.scale === "number" && Number.isFinite(value.scale)
    ? Math.max(0.35, Math.min(2.5, value.scale)) : fallback.scale;
  return {
    rotationY,
    offsetY,
    scale,
    poseMode: value?.poseMode === "original" ? "original" : "relaxed",
  };
}

export function getPersistedAvatarPresentation(modelUrl: string): AvatarPresentation {
  if (typeof window === "undefined") return defaultAvatarPresentation(modelUrl);
  try {
    const values = JSON.parse(window.localStorage.getItem(AVATAR_PRESENTATION_STORAGE_KEY) ?? "{}") as Record<string, Partial<AvatarPresentation>>;
    return normalizeAvatarPresentation(values[modelUrl], modelUrl);
  } catch {
    return defaultAvatarPresentation(modelUrl);
  }
}

export function persistAvatarPresentation(modelUrl: string, value: AvatarPresentation): void {
  try {
    const values = JSON.parse(window.localStorage.getItem(AVATAR_PRESENTATION_STORAGE_KEY) ?? "{}") as Record<string, AvatarPresentation>;
    values[modelUrl] = normalizeAvatarPresentation(value, modelUrl);
    window.localStorage.setItem(AVATAR_PRESENTATION_STORAGE_KEY, JSON.stringify(values));
  } catch {
    // The live avatar remains usable if browser storage is unavailable.
  }
}

export function flipAvatarFacing(value: AvatarPresentation): AvatarPresentation {
  const fullTurn = Math.PI * 2;
  const next = (value.rotationY + Math.PI) % fullTurn;
  return { ...value, rotationY: next < 0 ? next + fullTurn : next };
}
