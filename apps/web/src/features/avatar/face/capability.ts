import { ARKIT_COUNT, resolveArkitName, type ArkitName } from "./arkit";

export type ModelCapabilityKind =
  | "vrm-preset"       // VRM with only the standard presets
  | "vrm-perfectsync"  // VRM exposing ARKit-named custom expressions
  | "glb-arkit"        // plain GLB with ARKit-52 morph targets
  | "glb-basic";       // GLB without usable face morphs (body motion only)

export interface ModelCapability {
  kind: ModelCapabilityKind;
  /** ARKit names present on the model, mapped from the model's own spelling. */
  arkit: ReadonlyMap<ArkitName, string>;
  /** Fraction of the 52 ARKit shapes present (0..1). */
  arkitCoverage: number;
  hasVrmPresets: boolean;
  hasArkit: boolean;
}

/** A face needs at least these to look right when driven by ARKit weights alone. */
const CORE_ARKIT: ArkitName[] = ["eyeBlinkLeft", "eyeBlinkRight", "jawOpen", "mouthSmileLeft", "mouthSmileRight"];
/** Minimum coverage before a model is treated as ARKit-driven. */
export const ARKIT_MIN_COVERAGE = 0.4;

export interface CapabilityInput {
  isVrm: boolean;
  /** VRM expression names or GLB morph target names (union across meshes). */
  names: Iterable<string>;
}

export function detectModelCapability({ isVrm, names }: CapabilityInput): ModelCapability {
  const arkit = new Map<ArkitName, string>();
  for (const raw of names) {
    const resolved = resolveArkitName(raw);
    if (resolved && !arkit.has(resolved)) arkit.set(resolved, raw);
  }
  const arkitCoverage = arkit.size / ARKIT_COUNT;
  const hasCore = CORE_ARKIT.every((n) => arkit.has(n));
  const hasArkit = arkitCoverage >= ARKIT_MIN_COVERAGE && hasCore;
  const kind: ModelCapabilityKind = isVrm
    ? hasArkit ? "vrm-perfectsync" : "vrm-preset"
    : hasArkit ? "glb-arkit" : "glb-basic";
  return { kind, arkit, arkitCoverage, hasVrmPresets: isVrm, hasArkit };
}

export const isGlbUrl = (url: string): boolean => /\.(glb|gltf)(\?|#|$)/i.test(url);
