/**
 * vrmOptimizer — runtime GPU-load reduction for the VRM avatar.
 *
 * The Libby_free model ships ~33 textures (several 2048×2048 → ~176 MB VRAM)
 * and 456 morph targets (57 per face primitive × 8) even though the app only
 * drives the 14 VRM preset expressions. Two guarded passes fix both:
 * * 1. downscaleVrmTextures  — re-encodes textures above `maxTextureSize` on a
 *     canvas and swaps them in-place, preserving colorSpace/wrap/flipY/filters.
 *  2. pruneVrmMorphTargets  — keeps only the morph targets actually bound by
 *     the expressions the app drives, rebuilds the mesh morph dictionary and
 *     influences, and re-indexes the expression binds so lip-sync / emotions /
 *     blink keep working after the prune.
 *
 * NOTE (ordering invariant): prune assumes `VRMUtils.removeUnnecessaryVertices`
 * and `VRMUtils.combineSkeletons` ran first and preserved mesh identity — the
 * expression binds reference Mesh objects by reference, and those passes only
 * swap geometry / rebind bones without replacing the meshes.
 *
 * Both passes are individually guarded: a quirky model simply keeps its
 * original resources instead of crashing the frame.
 */
import * as THREE from "three";
import type { VRM } from "@pixiv/three-vrm";

export interface VrmOptimizeOptions {
  /** Max texture edge length after downscale (default 1024). */
  maxTextureSize?: number;
  /** Expression names whose morph binds must be preserved (default VRM presets). */
  keepExpressionNames?: readonly string[];
}

const DEFAULT_MAX_TEXTURE_SIZE = 1024;

const DEFAULT_KEEP_EXPRESSIONS: readonly string[] = [
  "happy",
  "angry",
  "sad",
  "relaxed",
  "surprised",
  "neutral",
  "blink",
  "blinkLeft",
  "blinkRight",
  "aa",
  "ih",
  "ou",
  "ee",
  "oh",
];

type MorphAttribute =
  | THREE.BufferAttribute
  | THREE.InterleavedBufferAttribute;

/** Shape of a morph-target bind inside a VRMExpression (duck-typed). */
interface MorphBind {
  primitives: THREE.Mesh[];
  index: number;
  weight: number;
}

function isMesh(object: THREE.Object3D): object is THREE.Mesh {
  return (object as THREE.Mesh).isMesh === true;
}

/** Collect every distinct texture reachable from the scene's materials. */
function collectTextures(vrm: VRM): Set<THREE.Texture> {
  const textures = new Set<THREE.Texture>();
  vrm.scene.traverse((object) => {
    if (!isMesh(object)) return;
    const materials = Array.isArray(object.material)
      ? object.material
      : [object.material];
    for (const material of materials) {
      if (!material) continue;
      for (const value of Object.values(material)) {
        if (value instanceof THREE.Texture) textures.add(value);
      }
    }
  });
  return textures;
}

function downscaleTexture(
  texture: THREE.Texture,
  maxSize: number,
): THREE.Texture | null {
  const image = texture.image as
    | { width?: number; height?: number }
    | undefined;
  if (!image || typeof image.width !== "number" || typeof image.height !== "number") {
    return null;
  }
  const largestEdge = Math.max(image.width, image.height);
  if (largestEdge <= maxSize) return null;

  const scale = maxSize / largestEdge;
  const width = Math.max(1, Math.round(image.width * scale));
  const height = Math.max(1, Math.round(image.height * scale));

  let canvas: HTMLCanvasElement;
  try {
    canvas = document.createElement("canvas");
  } catch {
    return null; // No DOM (SSR/worker) — skip.
  }
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return null;

  context.drawImage(texture.image as CanvasImageSource, 0, 0, width, height);

  const next = new THREE.CanvasTexture(canvas);
  // Preserve sampling semantics so the material looks identical.
  next.colorSpace = texture.colorSpace;
  next.wrapS = texture.wrapS;
  next.wrapT = texture.wrapT;
  next.flipY = texture.flipY;
  next.minFilter = texture.minFilter;
  next.magFilter = texture.magFilter;
  next.generateMipmaps = texture.generateMipmaps;
  next.anisotropy = texture.anisotropy;
  next.needsUpdate = true;
  return next;
}

/**
 * Pass 1 — re-encode every texture whose largest edge exceeds `maxSize`.
 * Mutates the scene materials in place (old textures are disposed).
 *
 * @returns the number of material slots replaced.
 */
export function downscaleVrmTextures(
  vrm: VRM,
  maxSize = DEFAULT_MAX_TEXTURE_SIZE,
): number {
  let downscaled = 0;
  for (const texture of collectTextures(vrm)) {
    const next = downscaleTexture(texture, maxSize);
    if (!next) continue;

    vrm.scene.traverse((object) => {
      if (!isMesh(object)) return;
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
      for (const material of materials) {
        if (!material) continue;
        // Duck-typed: only texture-typed material slots are replaced.
        const slots = material as unknown as Record<string, unknown>;
        for (const key of Object.keys(slots)) {
          if (slots[key] === texture) {
            slots[key] = next;
            downscaled += 1;
          }
        }
      }
    });

    try {
      texture.dispose();
    } catch {
      // Non-fatal: orphaned GPU memory is reclaimed on context teardown.
    }
  }
  return downscaled;
}

/**
 * Pass 2 — drop morph targets no expression bind references, then re-index
 * every bind so `morphTargetInfluences` still points at the right delta.
 *
 * three r185 stores `morphTargetDictionary` and `morphTargetInfluences` on the
 * Mesh, so after rebuilding `geometry.morphAttributes` we call
 * `mesh.updateMorphTargets()` to keep them consistent.
 *
 * @returns the number of morph targets removed.
 */
export function pruneVrmMorphTargets(
  vrm: VRM,
  keepExpressionNames = DEFAULT_KEEP_EXPRESSIONS,
): number {
  const manager = vrm.expressionManager;
  if (!manager) return 0;

  const keepNames = new Set(keepExpressionNames);

  // 1. Collect every (mesh, index) pair referenced by a kept expression.
  const usedIndices = new Map<string, Set<number>>();
  const binds: MorphBind[] = [];

  for (const expression of manager.expressions) {
    if (!expression || !keepNames.has(expression.name)) continue;
    const expressionBinds = expression.binds as unknown as MorphBind[] | undefined;
    if (!Array.isArray(expressionBinds)) continue;
    for (const bind of expressionBinds) {
      if (!bind || !Array.isArray(bind.primitives) || typeof bind.index !== "number") {
        continue;
      }
      binds.push(bind);
      for (const mesh of bind.primitives) {
        if (!mesh?.uuid) continue;
        const set = usedIndices.get(mesh.uuid) ?? new Set<number>();
        set.add(bind.index);
        usedIndices.set(mesh.uuid, set);
      }
    }
  }

  // 2. For each mesh with morph targets, rebuild attributes keeping only used
  //    indices and remap old → new index.
  const remaps = new Map<string, Map<number, number>>();
  let removed = 0;
  vrm.scene.traverse((object) => {
    if (!isMesh(object)) return;
    const mesh = object as THREE.Mesh;
    const geometry = mesh.geometry as THREE.BufferGeometry;
    const positionMorphs = geometry.morphAttributes.position;
    if (!positionMorphs || positionMorphs.length === 0) return;

    const total = positionMorphs.length;
    const wanted = usedIndices.get(mesh.uuid);
    const keep = new Set<number>();
    if (wanted) {
      for (const index of wanted) {
        if (index >= 0 && index < total) keep.add(index);
      }
    }
    // Keep at least one morph so the attribute array stays non-empty for
    // three.js (a zero-length morph list is invalid).
    if (keep.size === 0 && total > 0) keep.add(0);
    if (keep.size === total) {
      remaps.set(mesh.uuid, new Map(Array.from({ length: total }, (_, i) => [i, i])));
      return;
    }

    const oldToNew = new Map<number, number>();
    const newPosition: MorphAttribute[] = [];
    for (let i = 0; i < total; i += 1) {
      if (keep.has(i)) {
        oldToNew.set(i, newPosition.length);
        newPosition.push(positionMorphs[i]);
      }
    }
    removed += total - newPosition.length;

    const normalMorphs = geometry.morphAttributes.normal;
    if (normalMorphs && normalMorphs.length === total) {
      const newNormal: MorphAttribute[] = [];
      for (let i = 0; i < total; i += 1) {
        if (oldToNew.has(i)) newNormal.push(normalMorphs[i]);
      }
      geometry.morphAttributes.normal = newNormal;
    } else if (normalMorphs && normalMorphs.length > 0) {
      // Position morphs were pruned but the normal list has a different
      // length — leave a consistent empty list rather than misaligned
      // arrays (the renderer reads both by the same index).
      geometry.morphAttributes.normal = [];
    }

    // Rebuild geometry morphs, then keep the mesh morph state consistent
    // (r185 stores the dictionary + influences on Mesh). Preserve the
    // original dictionary names and re-map them to the new indices.
    geometry.morphAttributes.position = newPosition;
    const oldDictionary = mesh.morphTargetDictionary;
    if (oldDictionary) {
      const rebuilt: Record<string, number> = {};
      for (const [name, index] of Object.entries(oldDictionary)) {
        const nextIndex = oldToNew.get(index);
        if (nextIndex !== undefined) rebuilt[name] = nextIndex;
      }
      mesh.morphTargetDictionary = rebuilt;
    }
    // Match three's own convention: `updateMorphTargets()` allocates a plain
    // array, and r185 types `Mesh.morphTargetInfluences` as `number[]`.
    mesh.morphTargetInfluences = new Array<number>(newPosition.length).fill(0);
    remaps.set(mesh.uuid, oldToNew);
  });

  // 3. Re-index every collected bind. A bind applies `index` uniformly to ALL
  //    its primitives, so only re-index when every primitive maps the old
  //    index to the same new index — otherwise leave the bind untouched
  //    (mismatched layouts would point at the wrong morph for some meshes).
  for (const bind of binds) {
    if (bind.primitives.length === 0) continue;
    let nextIndex: number | undefined;
    let consistent = true;
    for (const mesh of bind.primitives) {
      const remap = remaps.get(mesh.uuid);
      if (!remap) {
        consistent = false;
        break;
      }
      const candidate = remap.get(bind.index);
      if (candidate === undefined) {
        consistent = false;
        break;
      }
      if (nextIndex === undefined) {
        nextIndex = candidate;
      } else if (nextIndex !== candidate) {
        consistent = false;
        break;
      }
    }
    if (consistent && nextIndex !== undefined && nextIndex !== bind.index) {
      bind.index = nextIndex;
    }
  }

  return removed;
}

/** Run both passes; returns a small report for diagnostics. */
export function optimizeVrm(
  vrm: VRM,
  options: VrmOptimizeOptions = {},
): { texturesDownscaled: number; morphTargetsRemoved: number } {
  let texturesDownscaled = 0;
  let morphTargetsRemoved = 0;
  try {
    texturesDownscaled = downscaleVrmTextures(
      vrm,
      options.maxTextureSize ?? DEFAULT_MAX_TEXTURE_SIZE,
    );
  } catch {
    // Non-fatal.
  }
  try {
    morphTargetsRemoved = pruneVrmMorphTargets(
      vrm,
      options.keepExpressionNames ?? DEFAULT_KEEP_EXPRESSIONS,
    );
  } catch {
    // Non-fatal.
  }
  return { texturesDownscaled, morphTargetsRemoved };
}
