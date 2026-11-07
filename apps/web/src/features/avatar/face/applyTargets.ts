import { ARKIT_BLENDSHAPES, resolveArkitName, type ArkitName } from "./arkit";
import type { ModelCapability } from "./capability";

/** Minimal slice of three's Mesh so this stays unit-testable without WebGL. */
export interface MorphMeshLike {
  morphTargetDictionary?: Record<string, number>;
  morphTargetInfluences?: number[];
}

export interface MorphBinding {
  influences: number[];
  index: number;
}

export type MorphBindings = Map<ArkitName, MorphBinding[]>;

/** Collect every mesh morph target that resolves to an ARKit name (faces are often split across meshes). */
export function buildMorphBindings(meshes: Iterable<MorphMeshLike>): MorphBindings {
  const out: MorphBindings = new Map();
  for (const mesh of meshes) {
    const dict = mesh.morphTargetDictionary;
    const infl = mesh.morphTargetInfluences;
    if (!dict || !infl) continue;
    for (const [name, index] of Object.entries(dict)) {
      const arkit = resolveArkitName(name);
      if (!arkit) continue;
      const list = out.get(arkit) ?? [];
      list.push({ influences: infl, index });
      out.set(arkit, list);
    }
  }
  return out;
}

export function collectMorphNames(meshes: Iterable<MorphMeshLike>): string[] {
  const names = new Set<string>();
  for (const m of meshes) for (const k of Object.keys(m.morphTargetDictionary ?? {})) names.add(k);
  return [...names];
}

export function applyArkitToMorphs(bindings: MorphBindings, weights: Partial<Record<ArkitName, number>>): void {
  for (const [name, list] of bindings) {
    const w = weights[name] ?? 0;
    for (const b of list) b.influences[b.index] = w;
  }
}

export interface ExpressionManagerLike {
  setValue(name: string, weight: number): void;
}

/**
 * Drive PerfectSync-style custom VRM expressions. Only names the model actually exposes are written.
 * `skip` lets the caller leave channels owned by the legacy preset pipeline (e.g. blink) alone.
 */
export function applyArkitToExpressions(
  em: ExpressionManagerLike,
  capability: ModelCapability,
  weights: Partial<Record<ArkitName, number>>,
  skip?: ReadonlySet<ArkitName>,
): void {
  for (const name of ARKIT_BLENDSHAPES) {
    const modelName = capability.arkit.get(name);
    if (!modelName || skip?.has(name)) continue;
    try { em.setValue(modelName, weights[name] ?? 0); } catch { /* expression may have been pruned */ }
  }
}
