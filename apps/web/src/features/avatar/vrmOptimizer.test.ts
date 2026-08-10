import { describe, expect, it, afterEach, vi } from "vitest";
import * as THREE from "three";
import {
  downscaleVrmTextures,
  optimizeVrm,
  pruneVrmMorphTargets,
} from "./vrmOptimizer";

/**
 * Build a minimal VRM-shaped object with a real THREE scene:
 *  - one mesh with 5 morph targets (happy, aa, blink, sad, custom)
 *  - an expression manager with expressions binding a subset of them
 */
function makeVrm() {
  const position = () => new THREE.BufferAttribute(new Float32Array(3), 3);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", position());
  geometry.morphAttributes.position = [
    position(),
    position(),
    position(),
    position(),
    position(),
  ];

  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial());
  // r185: dictionary + influences live on the Mesh.
  mesh.morphTargetDictionary = {
    happy: 0,
    aa: 1,
    blink: 2,
    sad: 3,
    custom: 4,
  };
  mesh.morphTargetInfluences = [0, 0, 0, 0, 0];
  const scene = new THREE.Scene();
  scene.add(mesh);

  const bind = (index: number) => ({ primitives: [mesh], index, weight: 1 });
  // One expression per dictionary entry: names match, binds point at the
  // matching morph index.
  const expressions = [
    { name: "happy", binds: [bind(0)], weight: 0 },
    { name: "aa", binds: [bind(1)], weight: 0 },
    { name: "blink", binds: [bind(2)], weight: 0 },
    { name: "sad", binds: [bind(3)], weight: 0 },
    { name: "custom", binds: [bind(4)], weight: 0 },
  ];
  const expressionManager = {
    expressions,
    getExpression: (name: string) =>
      expressions.find((e) => e.name === name) ?? null,
    setValue: (name: string, weight: number) => {
      const e = expressions.find((x) => x.name === name);
      if (e) e.weight = weight;
    },
  };

  return {
    vrm: { scene, expressionManager } as unknown as Parameters<
      typeof pruneVrmMorphTargets
    >[0],
    mesh,
    geometry,
    expressions,
  };
}

describe("pruneVrmMorphTargets", () => {
  afterEach(() => vi.restoreAllMocks());

  it("keeps only the morphs bound by kept expressions and re-indexes binds", () => {
    const { vrm, geometry, mesh, expressions } = makeVrm();

    const removed = pruneVrmMorphTargets(vrm, ["happy", "aa", "blink"]);

    // sad + custom dropped → 5 - 2 = 3 removed from total; only bound kept.
    expect(removed).toBe(2);
    expect(geometry.morphAttributes.position).toHaveLength(3);
    expect(mesh.morphTargetDictionary).toEqual({
      happy: 0,
      aa: 1,
      blink: 2,
    });
    expect(mesh.morphTargetInfluences).toHaveLength(3);

    // Binds now point at contiguous indices.
    expect(expressions[0].binds[0].index).toBe(0); // happy
    expect(expressions[1].binds[0].index).toBe(1); // aa
    expect(expressions[2].binds[0].index).toBe(2); // blink
  });

  it("re-indexes binds correctly when kept indices are non-contiguous", () => {
    const { vrm, geometry, mesh, expressions } = makeVrm();

    pruneVrmMorphTargets(vrm, ["happy", "sad", "custom"]);

    // happy(0), sad(3), custom(4) → new indices 0,1,2
    expect(geometry.morphAttributes.position).toHaveLength(3);
    expect(mesh.morphTargetDictionary).toEqual({
      happy: 0,
      sad: 1,
      custom: 2,
    });
    // The sad bind now points at index 1.
    expect(expressions[3].binds[0].index).toBe(1);
  });

  it("keeps at least one morph when nothing is bound (three.js safety)", () => {
    const { vrm, geometry, mesh } = makeVrm();

    const removed = pruneVrmMorphTargets(vrm, ["nonexistent"]);

    expect(geometry.morphAttributes.position).toHaveLength(1);
    expect(mesh.morphTargetDictionary).toEqual({ happy: 0 });
    expect(mesh.morphTargetInfluences).toHaveLength(1);
    expect(removed).toBe(4);
  });

  it("is a no-op when every morph is bound", () => {
    const { vrm, geometry, mesh } = makeVrm();

    const removed = pruneVrmMorphTargets(vrm, [
      "happy",
      "aa",
      "blink",
      "sad",
      "custom",
    ]);

    expect(geometry.morphAttributes.position).toHaveLength(5);
    expect(mesh.morphTargetDictionary).toEqual({
      happy: 0,
      aa: 1,
      blink: 2,
      sad: 3,
      custom: 4,
    });
    expect(mesh.morphTargetInfluences).toHaveLength(5);
    expect(removed).toBe(0);
  });

  it("returns 0 when the model has no expression manager", () => {
    const { vrm, geometry } = makeVrm();
    (vrm as { expressionManager: unknown }).expressionManager = null;
    const removed = pruneVrmMorphTargets(vrm, ["happy"]);
    expect(removed).toBe(0);
    expect(geometry.morphAttributes.position).toHaveLength(5);
  });
});

describe("downscaleVrmTextures", () => {
  afterEach(() => vi.restoreAllMocks());

  it("leaves textures at or under the max size untouched", () => {
    const { vrm, mesh } = makeVrm();
    const texture = new THREE.Texture({ width: 512, height: 512 } as ImageData);
    const material = mesh.material as THREE.MeshStandardMaterial;
    material.map = texture;

    const count = downscaleVrmTextures(vrm, 1024);

    expect(count).toBe(0);
    expect(material.map).toBe(texture);
  });

  it("skips gracefully when a 2D canvas context is unavailable", () => {
    const { vrm, mesh } = makeVrm();
    const texture = new THREE.Texture({ width: 2048, height: 2048 } as ImageData);
    const material = mesh.material as THREE.MeshStandardMaterial;
    material.map = texture;

    // jsdom returns null from getContext("2d") — the pass must not throw and
    // must leave the original texture in place.
    const count = downscaleVrmTextures(vrm, 1024);
    expect(count).toBe(0);
    expect(material.map).toBe(texture);
  });

  it("replaces an oversized texture with a downscaled CanvasTexture", () => {
    const { vrm, mesh } = makeVrm();
    const texture = new THREE.Texture({ width: 2048, height: 2048 } as ImageData);
    const disposeSpy = vi.spyOn(texture, "dispose");
    const material = mesh.material as THREE.MeshStandardMaterial;
    material.map = texture;

    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    const fakeContext = { drawImage: vi.fn() } as unknown as CanvasRenderingContext2D;
    const override = (function (this: HTMLCanvasElement, id: string) {
      return id === "2d"
        ? fakeContext
        : originalGetContext.call(this, id as "2d" | "bitmaprenderer" | "webgl" | "webgl2");
    }) as typeof HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = override;
    try {
      const count = downscaleVrmTextures(vrm, 1024);
      expect(count).toBe(1);
      expect(material.map).not.toBe(texture);
      expect(material.map).toBeInstanceOf(THREE.CanvasTexture);
      expect(disposeSpy).toHaveBeenCalled();
    } finally {
      HTMLCanvasElement.prototype.getContext = originalGetContext;
    }
  });
});

describe("optimizeVrm", () => {
  it("runs both passes and reports counts", () => {
    const { vrm, geometry } = makeVrm();

    const report = optimizeVrm(vrm, {
      keepExpressionNames: ["happy", "aa", "blink"],
    });

    expect(report.morphTargetsRemoved).toBe(2);
    expect(geometry.morphAttributes.position).toHaveLength(3);
  });
});
